# Write-up: VM vs. App Service for the Article CMS

## Analyze, choose, and justify the appropriate resource option for deploying the app.

### Option 1: Azure Virtual Machine (IaaS)

**Cost.** You pay for the VM around the clock regardless of traffic (e.g. a
B1s burstable VM is billed hourly whether or not anyone visits the site),
plus a separate managed disk and a public IP. There is no automatic
scale-to-zero, so cost is roughly constant and you are responsible for
sizing it correctly up front.

**Scalability.** Scaling is manual and coarse-grained: resizing the VM SKU
requires a reboot, and horizontal scaling means standing up a Virtual
Machine Scale Set plus a load balancer yourself. There is no built-in
autoscale rule tied to CPU/HTTP queue length the way App Service offers out
of the box.

**Availability.** A single VM is a single point of failure — an OS patch,
reboot, or hardware fault takes the site down unless you additionally
configure an Availability Set/Zone and a second instance behind a load
balancer, which is extra setup and cost.

**Workflow.** You own the whole stack: OS patching, installing Python and
the ODBC driver, configuring IIS/Gunicorn + nginx or Apache as a reverse
proxy, opening firewall ports, and setting up your own deployment
mechanism (e.g. `git pull` + service restart, or a CI script over SSH).
This is flexible — you can run anything, including background workers or
custom system packages — but it is meaningfully more operational overhead
for a simple Flask CRUD app.

### Option 2: Azure App Service (PaaS)

**Cost.** Billed by the App Service Plan tier (e.g. B1) rather than by the
individual app, and a single plan can host multiple apps. The Free/Shared
and Basic tiers make small apps like this one inexpensive, and you are not
responsible for the cost of an underlying OS disk or patch-management
tooling — that is bundled into the platform.

**Scalability.** Built-in vertical scaling (change the plan's tier) and
horizontal autoscale (scale out on CPU/HTTP queue metrics or a schedule)
are configured with a few clicks/az-cli commands, with no VM images or
load balancers to manage.

**Availability.** The platform handles OS patching, and moving to a
Standard+ tier adds multiple instances and zone redundancy without the app
owner having to build that topology by hand the way you would for a VM.

**Workflow.** Deployment is native to how this project already ships code:
push to GitHub and use App Service's GitHub Actions/Deployment Center
integration (a `.github/workflows` folder is already present in this
repo), or `az webapp up` / zip-deploy from the CLI. `requirements.txt` is
picked up automatically by the Python runtime via Oryx build, `SECRET_KEY`,
`SQL_*`, `BLOB_*`, `CLIENT_ID`/`CLIENT_SECRET` are set as App Settings
(environment variables) instead of being hand-edited into `config.py`, and
`web.config`/startup command handles the WSGI entry point. Logs are
available directly through the Log Stream / App Service Logs blade, which
is exactly the mechanism the rubric asks for as evidence of login logging.

### Choice: App Service

For this specific application — a small, stateless Flask CRUD app with no
custom OS-level dependencies, whose data and files already live in managed
Azure SQL and Blob Storage rather than on local disk — **App Service is the
appropriate choice**. It removes OS/patch management entirely, its
plan-based pricing is cheaper for a low-traffic CMS than paying for an
always-on VM, its autoscale and multi-instance availability options are
configured declaratively instead of hand-built, and its native GitHub
deployment plus Log Stream integration line up directly with how this
project is already structured and how the rubric expects login attempts to
be evidenced (Azure Log Stream). Since the app is stateless (sessions are
stored server-side via `flask-session`, and all persistent data lives in
Azure SQL/Blob rather than on the local filesystem), it is a natural fit
for App Service's model of ephemeral, horizontally-scalable instances.

## Assess app changes that would change your decision.

A VM would become the better choice if the app needed capabilities App
Service's sandboxed runtime does not give you directly, for example:

- **Custom system-level dependencies** — e.g. a non-standard ODBC driver
  version, GPU access, or a background daemon that needs to run outside
  the request/response lifecycle (App Service does support WebJobs, but a
  VM gives unrestricted control).
- **Full network/OS control** — if the app needed a custom reverse-proxy
  configuration, non-HTTP protocols, or fine-grained OS-level security
  hardening/compliance requirements that App Service's managed platform
  does not expose.
- **Local, persistent disk state** — if the app wrote large files to local
  disk that had to survive instance restarts without being moved to Blob
  Storage first (App Service's local storage is not guaranteed persistent
  across scale/restart events the way a VM's attached disk is).
- **Cost at very large, predictable, always-on scale** — at a large enough
  and sufficiently steady traffic volume, reserved-instance VM pricing (or
  VMSS with reserved instances) can undercut the equivalent App Service
  Premium tier, though this app's traffic profile does not come close to
  that threshold.

None of these apply to the current Article CMS, which is why App Service
remains the right call today.

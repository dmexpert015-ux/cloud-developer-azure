"""
The flask application package.
"""
import logging
from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_session import Session

app = Flask(__name__)
app.config.from_object(Config)

# Configure app logging so both successful and unsuccessful login attempts
# are captured. Azure App Service / VM deployments surface stdout through
# the Log Stream, so a StreamHandler is enough to satisfy that requirement;
# it also keeps local development logs visible in the console.
app.logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    app.logger.addHandler(stream_handler)
app.logger.info('Article CMS startup')

Session(app)
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = 'login'

import FlaskWebProject.views

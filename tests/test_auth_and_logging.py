"""
Unit tests for the two areas of the project that were TODOs in the
starter code: the msal-based "Sign in with Microsoft" flow (views.py)
and login-attempt logging (__init__.py / views.py).

These tests run entirely locally against an in-memory SQLite database and
mock out msal's network calls, so they do not require any live Azure SQL,
Blob Storage, or Azure AD app registration. They exist to prove the
implemented code is correct, independent of whether live Azure resources
are available in a given environment.
"""
import logging
import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")

from FlaskWebProject import app, db
from FlaskWebProject.models import User
from FlaskWebProject import views


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SERVER_NAME"] = "localhost"

    with app.app_context():
        db.create_all()
        admin = User(username="admin")
        admin.set_password("pass")
        db.session.add(admin)
        db.session.commit()

        with app.test_client() as test_client:
            yield test_client

        db.session.remove()
        db.drop_all()


def test_invalid_form_login_is_logged_as_warning(client, caplog):
    with caplog.at_level(logging.WARNING, logger="FlaskWebProject"):
        response = client.post(
            "/login",
            data={"username": "admin", "password": "wrong-password"},
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert any(
        "Invalid login attempt" in record.message for record in caplog.records
    )


def test_valid_form_login_is_logged_as_info(client, caplog):
    with caplog.at_level(logging.INFO, logger="FlaskWebProject"):
        response = client.post(
            "/login",
            data={"username": "admin", "password": "pass"},
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert any(
        "admin logged in successfully" in record.message
        for record in caplog.records
    )


def test_build_msal_app_returns_confidential_client_application():
    msal_app = views._build_msal_app()
    assert type(msal_app).__name__ == "ConfidentialClientApplication"


def test_build_auth_url_includes_redirect_uri_and_state():
    with app.test_request_context("/login"):
        auth_url = views._build_auth_url(scopes=["User.Read"], state="test-state")
    assert auth_url is not None
    assert "state=test-state" in auth_url
    assert "getAToken" in auth_url  # matches Config.REDIRECT_PATH


def test_load_and_save_cache_round_trip_via_session():
    with app.test_request_context("/login"):
        from flask import session

        cache = views._load_cache()
        assert cache.has_state_changed is False

        # Simulate msal writing a token into the cache.
        cache.add(
            {
                "response": {
                    "token_type": "Bearer",
                    "scope": "User.Read",
                    "expires_in": 3600,
                    "access_token": "fake-access-token",
                    "id_token": "fake-id-token",
                    "id_token_claims": {
                        "preferred_username": "admin",
                        "sub": "fake-subject-id",
                    },
                },
                "client_id": "test-client-id",
                "scope": ["User.Read"],
            }
        )
        views._save_cache(cache)
        assert "token_cache" in session

        reloaded = views._load_cache()
        assert reloaded.find("IdToken")


def test_authorized_route_logs_and_rejects_on_msal_error(client, caplog):
    with client.session_transaction() as sess:
        sess["state"] = "abc123"

    fake_app = MagicMock()
    fake_app.acquire_token_by_authorization_code.return_value = {
        "error": "invalid_grant",
        "error_description": "AADSTS70008: expired auth code",
    }

    with patch.object(views, "_build_msal_app", return_value=fake_app):
        with caplog.at_level(logging.WARNING, logger="FlaskWebProject"):
            response = client.get(
                "/getAToken?code=fake-code&state=abc123", follow_redirects=True
            )

    assert response.status_code == 200
    assert any(
        "Invalid login attempt via Microsoft sign-in" in record.message
        for record in caplog.records
    )


def test_authorized_route_logs_in_admin_on_msal_success(client, caplog):
    with client.session_transaction() as sess:
        sess["state"] = "abc123"

    fake_app = MagicMock()
    fake_app.acquire_token_by_authorization_code.return_value = {
        "id_token_claims": {"preferred_username": "admin"}
    }

    with patch.object(views, "_build_msal_app", return_value=fake_app):
        with caplog.at_level(logging.INFO, logger="FlaskWebProject"):
            response = client.get(
                "/getAToken?code=fake-code&state=abc123", follow_redirects=True
            )

    assert response.status_code == 200
    assert any(
        "admin logged in successfully via Microsoft sign-in" in record.message
        for record in caplog.records
    )

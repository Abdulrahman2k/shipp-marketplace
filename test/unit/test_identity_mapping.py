"""Fail-closed Databricks identity-to-profile mapping regression tests."""

import json

import pytest

from services.identity_service import verified_databricks_profile


USER_ID = "shipp-user-42"
PLATFORM_ID = "platform-user-42"
EMAIL = "maya@example.test"


class FakeAuthRepo:
    def __init__(self, profile=None):
        self.profile = profile

    def get_profile(self, user_id):
        if self.profile is None:
            raise LookupError("Profile not found")
        return self.profile


@pytest.fixture
def auth_repo():
    return FakeAuthRepo({
        "user_id": USER_ID,
        "name": "Maya",
        "roles": ["DONOR"],
    })


@pytest.fixture(autouse=True)
def setup_identity(monkeypatch):
    monkeypatch.setenv("SHIPP_DEPLOYMENT_TARGET", "databricks_app")
    monkeypatch.setenv(
        "SHIPP_DATABRICKS_IDENTITY_MAP",
        json.dumps({
            PLATFORM_ID: {
                "email": EMAIL,
                "user_id": USER_ID,
            },
        }),
    )


def valid_headers():
    return {
        "x-forwarded-user": PLATFORM_ID,
        "x-forwarded-email": EMAIL,
    }


def test_valid_identity(auth_repo):
    result = verified_databricks_profile(auth_repo, valid_headers())
    assert result["user_id"] == USER_ID


def test_unknown_platform_user(auth_repo):
    headers = valid_headers()
    headers["x-forwarded-user"] = "unknown"
    assert verified_databricks_profile(auth_repo, headers) is None


def test_wrong_email(auth_repo):
    headers = valid_headers()
    headers["x-forwarded-email"] = "other@example.test"
    assert verified_databricks_profile(auth_repo, headers) is None


def test_missing_headers(auth_repo):
    assert verified_databricks_profile(auth_repo, {}) is None


def test_missing_mapping(auth_repo, monkeypatch):
    monkeypatch.delenv("SHIPP_DATABRICKS_IDENTITY_MAP")
    assert verified_databricks_profile(auth_repo, valid_headers()) is None


def test_invalid_mapping_json(auth_repo, monkeypatch):
    monkeypatch.setenv("SHIPP_DATABRICKS_IDENTITY_MAP", "invalid-json")
    assert verified_databricks_profile(auth_repo, valid_headers()) is None


def test_missing_database_profile():
    assert verified_databricks_profile(FakeAuthRepo(), valid_headers()) is None


def test_database_profile_id_mismatch():
    repo = FakeAuthRepo({
        "user_id": "someone-else",
        "roles": ["DONOR"],
    })
    assert verified_databricks_profile(repo, valid_headers()) is None


def test_wrong_deployment_target(auth_repo, monkeypatch):
    monkeypatch.setenv("SHIPP_DEPLOYMENT_TARGET", "local")
    assert verified_databricks_profile(auth_repo, valid_headers()) is None

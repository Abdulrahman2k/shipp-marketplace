"""Role authorization boundaries for SHIPP donor and requester pages."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import services.identity_service as identity


@pytest.fixture
def fake_streamlit(monkeypatch):
    fake = SimpleNamespace(
        warning=Mock(),
        caption=Mock(),
        error=Mock(),
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    return fake


def test_donor_allowed(monkeypatch, fake_streamlit):
    monkeypatch.setattr(
        identity, "current_profile",
        lambda: {"user_id": "qa-donor-001", "roles": ["DONOR"]},
    )
    profile = identity.require_role("DONOR")
    assert profile["user_id"] == "qa-donor-001"
    fake_streamlit.error.assert_not_called()


def test_requester_cannot_donate(monkeypatch, fake_streamlit):
    monkeypatch.setattr(
        identity, "current_profile",
        lambda: {"user_id": "qa-requester-001", "roles": ["REQUESTER"]},
    )
    assert identity.require_role("DONOR") is None
    fake_streamlit.error.assert_called_once()


def test_missing_profile_denied(monkeypatch, fake_streamlit):
    monkeypatch.setattr(identity, "current_profile", lambda: None)
    assert identity.require_role("DONOR") is None
    fake_streamlit.warning.assert_called_once()


def test_dual_role_allowed(monkeypatch, fake_streamlit):
    monkeypatch.setattr(
        identity, "current_profile",
        lambda: {"user_id": "qa-both-001", "roles": ["DONOR", "REQUESTER"]},
    )
    profile = identity.require_role("DONOR")
    assert profile is not None
    assert "DONOR" in profile["roles"]

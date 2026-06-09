"""Smoke tests for Phoenix Agent."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    from phoenix_agent.main import app
    return TestClient(app)


def test_root_endpoint(client):
    """The root endpoint should identify the service."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "phoenix-agent"
    assert data["author"] == "Wiqi Lee"


def test_health_endpoint(client):
    """Health endpoint should return healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_strategies_registered():
    """All expected strategies should be registered."""
    from phoenix_agent.strategies import list_strategies

    strategies = list_strategies()
    assert "regenerate_lockfile" in strategies
    assert "auto_format" in strategies
    assert "quarantine_flaky_test" in strategies
    assert "fix_ci_yaml" in strategies

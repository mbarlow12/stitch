from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

import stitch.llm.main as main_module
from stitch.llm.main import app

_REQUEST_LOGGER = "stitch.observability.request"


@pytest.fixture
def test_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main_module, "validate_auth_config_at_startup", lambda: None)
    monkeypatch.setattr(
        main_module, "validate_downstream_auth_config_at_startup", lambda: None
    )
    with TestClient(app) as client:
        yield client


def _request_events(caplog) -> list[dict]:
    return [r.event for r in caplog.records if r.name == _REQUEST_LOGGER]


def test_health_request_sets_request_id_and_emits_summary(test_client, caplog) -> None:
    with caplog.at_level(logging.INFO, logger=_REQUEST_LOGGER):
        response = test_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]

    events = _request_events(caplog)
    assert len(events) == 1
    event = events[0]
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert event["method"] == "GET"
    assert event["route"] == "/api/v1/health"
    assert event["status_code"] == 200

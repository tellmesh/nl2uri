"""Tests for compact flow repair and validation."""

from __future__ import annotations

import pytest

from nl2uri.flow_repair import extract_flow_payload, repair_and_validate_flow, repair_flow_body, sanitize_flow_step
from nl2uri.graph_planner import wrap_nl2uri_output
from uri2flow import validate_expanded_flow


def test_extract_flow_payload_from_graph_nodes():
    raw = {
        "graph": {
            "id": "health",
            "nodes": [
                {
                    "id": "open_health",
                    "uri": "browser://chrome/page/open",
                    "operation": "open",
                    "payload": {"url": "http://localhost:8101/health"},
                },
                {
                    "id": "verify_ok",
                    "uri": "assertion://contains",
                    "operation": "check",
                    "depends_on": ["open_health"],
                },
            ],
        }
    }
    body = extract_flow_payload(raw)
    assert len(body["do"]) == 2
    assert body["do"][0]["uri"].startswith("browser://")
    assert body["do"][1]["after"] == "open_health"


def test_sanitize_flow_step_drops_unknown_scheme():
    warnings: list[str] = []
    assert sanitize_flow_step({"uri": "python://run"}, warnings=warnings, index=0) is None
    assert warnings


def test_repair_flow_body_from_task_steps():
    raw = {
        "task": {"id": "health"},
        "steps": [
            {"uri": "browser://chrome/page/open", "operation": "open_page", "payload": {"url": "http://x"}},
            {"uri": "mcp://tool/run", "operation": "run"},
        ],
    }
    body, warnings = repair_flow_body(raw, "check health")
    assert len(body["do"]) == 1
    assert body["do"][0]["with"]["url"] == "http://x"
    assert warnings


def test_validate_expanded_flow_accepts_weather_flow():
    payload = wrap_nl2uri_output(
        "uri_flow",
        "weather",
        {
            "flow": {"id": "weather-agent-health"},
            "do": [
                "agent://weather-generator",
                "hypervisor://local/weather-agent/run",
                {"browser://chrome/page/open": {"url": "http://localhost:8101/health"}},
            ],
        },
    )
    assert not validate_expanded_flow(payload)


def test_repair_and_validate_flow_branching():
    raw = {
        "flow": {"id": "check-agent"},
        "do": [
            {"id": "run_agent", "uri": "hypervisor://local/weather-agent/run"},
            {"id": "health", "uri": "http://localhost:8101/health", "after": "run_agent"},
            {
                "id": "logs_if_failed",
                "uri": "log://weather-map-agent.local?limit=100",
                "after": "health",
                "if": "health.ok == false",
            },
        ],
    }
    body, warnings = repair_and_validate_flow(raw, "check agent health", nl2uri_wrapper={"nl2uri": {"version": 1, "kind": "uri_flow", "source_prompt": "x"}})
    assert len(body["do"]) == 3
    assert body["do"][-1]["if"] == "health.ok == false"
    assert warnings is not None


def test_repair_and_validate_flow_rejects_empty():
    with pytest.raises(ValueError, match="no valid flow steps"):
        repair_and_validate_flow({"do": [{"uri": "python://run"}]}, "bad prompt")

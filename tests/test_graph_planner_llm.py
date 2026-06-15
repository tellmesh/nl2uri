"""Tests for LLM graph planner, repair, and fallback."""

from __future__ import annotations

from unittest.mock import patch

from nl2uri.graph_planner import plan_task, plan_workflow_graph
from nl2uri.graph_planner_llm import build_graph_planner_system_prompt, plan_graph_with_llm
from nl2uri.graph_repair import extract_graph_payload, repair_graph_body, sanitize_node
from uri3.graph import validate_workflow_graph


def test_build_graph_planner_system_prompt_includes_registry():
    prompt = build_graph_planner_system_prompt(kind="workflow_graph")
    assert "browser" in prompt
    assert "hypervisor" in prompt
    assert "assertion" in prompt
    assert "Do NOT invent handlers" in prompt


def test_sanitize_node_drops_unknown_scheme():
    warnings: list[str] = []
    assert sanitize_node({"id": "bad", "uri": "python://run", "operation": "run"}, warnings=warnings) is None
    assert any("unsupported scheme" in item for item in warnings)


def test_sanitize_node_coerces_operation():
    warnings: list[str] = []
    node = sanitize_node(
        {"id": "open", "uri": "browser://chrome/page/open", "operation": "open_page"},
        warnings=warnings,
    )
    assert node is not None
    assert node["operation"] == "open"


def test_repair_graph_body_from_task_shape():
    raw = {
        "task": {"id": "health"},
        "steps": [
            {"id": "open", "uri": "browser://chrome/page/open", "operation": "open_page", "payload": {"url": "http://x"}},
            {"id": "bad", "uri": "mcp://tool/run", "operation": "run"},
        ],
    }
    body, warnings = repair_graph_body(raw, "check health", kind="task_graph")
    assert len(body["steps"]) == 1
    assert body["steps"][0]["operation"] == "open"
    assert warnings


def test_extract_graph_payload_accepts_graph_nodes_top_level():
    raw = {"id": "wf", "nodes": [{"id": "a", "uri": "log://x", "operation": "read"}]}
    body = extract_graph_payload(raw)
    assert "graph" in body


@patch("nl2uri.graph_planner_llm.call_graph_planner_llm")
def test_plan_graph_with_llm_validates_output(mock_call):
    mock_call.return_value = {
        "graph": {
            "id": "health",
            "kind": "workflow",
            "nodes": [
                {
                    "id": "open_health",
                    "uri": "browser://chrome/page/open",
                    "operation": "open",
                    "kind": "command",
                    "payload": {"url": "http://localhost:8101/health"},
                },
                {
                    "id": "verify_ok",
                    "uri": "assertion://contains",
                    "operation": "check",
                    "kind": "assertion",
                    "depends_on": ["open_health"],
                    "payload": {"actual_from": "open_health.text", "expected": "ok"},
                },
            ],
        }
    }
    payload = plan_graph_with_llm("sprawdź health w Chrome", kind="workflow_graph")
    assert payload["nl2uri"]["kind"] == "workflow_graph"
    assert not validate_workflow_graph(payload)
    assert "planner_warning" not in payload


@patch("nl2uri.graph_planner_llm.call_graph_planner_llm")
def test_plan_graph_with_llm_fallback_on_invalid(mock_call):
    mock_call.return_value = {
        "graph": {
            "id": "bad",
            "nodes": [{"id": "x", "uri": "python://run", "operation": "run"}],
        }
    }
    payload = plan_graph_with_llm("otwórz Chrome i sprawdź health", kind="task_graph")
    assert payload["nl2uri"]["kind"] == "task_graph"
    assert "planner_warning" in payload
    assert "fallback" in payload["planner_warning"]


@patch("nl2uri.graph_planner_llm.call_graph_planner_llm")
def test_plan_task_use_llm_flag(mock_call):
    mock_call.return_value = {
        "task": {"id": "health"},
        "steps": [
            {
                "id": "open_health",
                "uri": "browser://chrome/page/open",
                "operation": "open",
                "kind": "command",
                "payload": {"url": "http://localhost:8101/health"},
            }
        ],
    }
    payload = plan_task("check health", use_llm=True)
    assert payload["steps"][0]["uri"].startswith("browser://")
    mock_call.assert_called_once()

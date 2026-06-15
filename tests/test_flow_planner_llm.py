"""Tests for LLM compact flow planner."""

from __future__ import annotations

from unittest.mock import patch

from nl2uri.flow_planner import plan_flow
from nl2uri.flow_planner_llm import build_flow_planner_system_prompt, plan_flow_with_llm


def test_build_flow_planner_system_prompt_includes_compact_shape():
    prompt = build_flow_planner_system_prompt()
    assert "compact URI flows" in prompt
    assert '"do"' in prompt
    assert "browser" in prompt
    assert "Do NOT invent unsupported URI schemes" in prompt


@patch("nl2uri.flow_planner_llm.call_flow_planner_llm")
def test_plan_flow_with_llm_validates_compact_output(mock_call):
    mock_call.return_value = {
        "flow": {"id": "weather-agent-health"},
        "do": [
            "agent://weather-generator",
            "hypervisor://local/weather-agent/run",
            {"uri": "browser://chrome/page/open", "with": {"url": "http://localhost:8101/health"}},
        ],
    }
    payload = plan_flow_with_llm("wygeneruj agenta pogodowego, uruchom go lokalnie i sprawdź health w Chrome")
    assert payload["nl2uri"]["kind"] == "uri_flow"
    assert payload["do"][0] == "agent://weather-generator"
    assert "planner_warning" not in payload


@patch("nl2uri.flow_planner_llm.call_flow_planner_llm")
def test_plan_flow_with_llm_converts_graph_nodes(mock_call):
    mock_call.return_value = {
        "graph": {
            "id": "health",
            "nodes": [
                {
                    "id": "open_health",
                    "uri": "browser://chrome/page/open",
                    "operation": "open",
                    "payload": {"url": "http://localhost:8101/health"},
                }
            ],
        }
    }
    payload = plan_flow_with_llm("sprawdź health w Chrome")
    assert payload["nl2uri"]["kind"] == "uri_flow"
    assert payload["do"][0]["uri"].startswith("browser://")


@patch("nl2uri.flow_planner_llm.call_flow_planner_llm")
def test_plan_flow_with_llm_fallback_on_invalid(mock_call):
    mock_call.return_value = {"do": [{"uri": "python://run"}]}
    payload = plan_flow_with_llm("sprawdź health")
    assert payload["nl2uri"]["kind"] == "uri_flow"
    assert "planner_warning" in payload
    assert "fallback" in payload["planner_warning"]


@patch("nl2uri.flow_planner_llm.plan_flow_with_llm")
def test_plan_flow_use_llm_flag(mock_plan):
    mock_plan.return_value = {"nl2uri": {"kind": "uri_flow"}, "flow": {"id": "x"}, "do": ["log://x"]}
    payload = plan_flow("check logs", use_llm=True)
    assert payload["nl2uri"]["kind"] == "uri_flow"
    mock_plan.assert_called_once()

"""Tests for nl2uri flow planner and classifier updates."""

from __future__ import annotations

from nl2uri.flow_planner import plan_flow
from nl2uri.graph_planner import plan_auto
from nl2uri.output_classifier import classify_output_kind
from uri2flow import expand_flow


WEATHER_PROMPT = "wygeneruj agenta pogodowego, uruchom go lokalnie i sprawdź health w Chrome"


def test_classify_uri_flow_for_sequential_process():
    assert classify_output_kind(WEATHER_PROMPT) == "uri_flow"


def test_classify_task_prompt_as_uri_flow():
    assert classify_output_kind("otwórz Chrome i sprawdź czy localhost:8101/health działa") == "uri_flow"


def test_classify_condition_stays_workflow_graph():
    prompt = "uruchom agenta, sprawdź health i jeśli nie działa zrestartuj go"
    assert classify_output_kind(prompt) == "workflow_graph"


def test_plan_flow_weather_prompt():
    payload = plan_flow(WEATHER_PROMPT)
    assert payload["nl2uri"]["kind"] == "uri_flow"
    assert payload["flow"]["id"]
    assert "agent://weather-generator" in payload["do"]
    assert "hypervisor://local/weather-agent/run" in payload["do"]
    browser_step = payload["do"][-1]
    assert isinstance(browser_step, dict)
    assert "browser://chrome/page/open" in browser_step
    assert browser_step["browser://chrome/page/open"]["url"] == "http://localhost:8101/health"


def test_weather_domain_registry_fragment_has_flow_aliases(repo_root):
    fragment = repo_root / "domains" / "weather_map" / "registry.fragment.yaml"
    text = fragment.read_text(encoding="utf-8")
    assert "flow_aliases:" in text
    assert "generator: weather-generator" in text
    assert "local_run: weather-agent" in text
    assert "default_health_uri: http://localhost:8101/health" in text


def test_plan_auto_prefers_uri_flow_for_weather():
    auto = plan_auto(WEATHER_PROMPT)
    assert auto["nl2uri"]["kind"] == "uri_flow"


def test_flow_expands_to_valid_workflow_graph():
    payload = plan_flow(WEATHER_PROMPT)
    graph = expand_flow(payload)
    assert graph["nl2uri"]["kind"] == "workflow_graph"
    assert graph["graph"]["nodes"]
    assert graph["graph"]["edges"]

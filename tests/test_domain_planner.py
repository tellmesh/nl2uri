"""Tests for domain planner LLM normalization."""

from __future__ import annotations

from nl2uri.domain_planner import _normalize_llm_tree, plan_from_prompt


BAD_LLM_TREE = {
    "domain": "domain://weather",
    "commands": ["command://weather.generate-forecast-map?range=2weeks&format=html"],
    "resources": ["resource://weather.forecast-data", "resource://map-rendering-engine"],
    "agent": "agent://weather-map-agent",
}


def test_normalize_bad_llm_weather_tree_uses_deterministic_template():
    tree = _normalize_llm_tree("generuj mape pogody dwa tygodnie do przodu w html", BAD_LLM_TREE)
    assert tree["domain"]["id"] == "weather_map"
    assert isinstance(tree["commands"], dict)
    assert "generate_weather_map" in tree["commands"]
    assert "deployment" in tree
    assert "planner_warning" in tree


def test_plan_from_prompt_weather_no_llm_full_tree():
    tree = plan_from_prompt("generuj mape pogody dwa tygodnie do przodu w html", use_llm=False)
    assert tree["domain"]["id"] == "weather_map"
    assert tree["inputs"]["days"]["default"] == 14
    assert "html_map" in tree["resources"]
    assert tree["agent"]["id"] == "weather-map-agent"
    assert tree["deployment"]["default"]["uri"] == "local://agents/generated/weather_map_agent"

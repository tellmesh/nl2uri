"""Tests for nl2uri multi-output graph planner."""

from __future__ import annotations

from nl2uri.graph_planner import plan_auto, plan_list, plan_single, plan_task, plan_tree, plan_workflow_graph
from nl2uri.output_classifier import classify_output_kind


def test_classify_resource_tree():
    assert classify_output_kind("wygeneruj domenę weather map z agentem i widokiem HTML") == "resource_tree"


def test_classify_task_graph():
    assert classify_output_kind("otwórz Chrome i sprawdź czy localhost:8101/health działa") == "uri_flow"


def test_classify_workflow_graph():
    prompt = "wygeneruj agenta pogodowego, uruchom go lokalnie i sprawdź health w Chrome"
    assert classify_output_kind(prompt) == "uri_flow"


def test_plan_single_status():
    payload = plan_single("pokaż status agenta pogodowego")
    assert payload["nl2uri"]["kind"] == "single_uri"
    assert payload["uri"] == "agent://weather-map-agent/status"


def test_plan_list_health_and_card():
    payload = plan_list("sprawdź health agenta pogodowego i pokaż jego agent card")
    assert payload["nl2uri"]["kind"] == "uri_list"
    assert len(payload["uris"]) >= 2


def test_plan_tree_contains_domain_root():
    payload = plan_tree("wygeneruj domenę weather map z agentem i widokiem HTML", use_llm=False)
    assert payload["tree"]["root"] == "domain://weather-map"
    assert "agent://weather-map-agent" in payload["tree"]["children"]


def test_plan_screenshot_schedule_stable_id():
    from nl2uri.graph_planner import WEBSITE_SCREENSHOT_SCHEDULE_ID, plan_screenshot_schedule

    prompt = (
        "rob rzuty ekranów stron softreck.com prototypowanie.pl www "
        "co 5 minut do folderu usera ~/images/"
    )
    payload = plan_screenshot_schedule(prompt)
    assert payload["flow"]["id"] == WEBSITE_SCREENSHOT_SCHEDULE_ID
    assert payload["task"]["id"] == WEBSITE_SCREENSHOT_SCHEDULE_ID
    assert len(payload["steps"]) == 4
    assert payload["flow"]["schedule_minutes"] == 5
    assert payload["flow"]["output_dir"] == "~/images/"


def test_plan_task_linear_steps():
    payload = plan_task("otwórz Chrome, przejdź do localhost:8101/health i sprawdź czy działa")
    assert payload["task"]["id"]
    assert payload["steps"][0]["uri"] == "browser://chrome/page/open"
    assert payload["steps"][-1]["depends_on"]


def test_plan_workflow_generate_run_check():
    prompt = "wygeneruj agenta pogodowego, uruchom go i sprawdź health"
    payload = plan_workflow_graph(prompt)
    node_ids = [node["id"] for node in payload["graph"]["nodes"]]
    assert "generate_domain" in node_ids
    assert "run_agent" in node_ids
    assert "verify_ok" in node_ids


def test_plan_auto_matches_classifier():
    prompt = "sprawdź health agenta pogodowego i pokaż jego agent card"
    auto = plan_auto(prompt)
    assert auto["nl2uri"]["kind"] == classify_output_kind(prompt)

from __future__ import annotations

import re
from typing import Any

from nl2uri.agent_resolution import (
    resolve_agent_id,
    resolve_card_uri,
    resolve_deployment_id,
    resolve_domain_uri,
    resolve_health_uri,
    resolve_log_uri,
)
from nl2uri.domain_planner import plan_from_prompt
from nl2uri.output_classifier import classify_output_kind

WEBSITE_SCREENSHOT_SCHEDULE_ID = "website-screenshot-schedule"
DEFAULT_SCREENSHOT_SITES = ("https://softreck.com", "https://prototypowanie.pl")


def _slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "task"


def wrap_nl2uri_output(kind: str, prompt: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "nl2uri": {
            "version": 1,
            "kind": kind,
            "source_prompt": prompt,
        },
        **body,
    }


def plan_single(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    del use_llm
    agent_id = resolve_agent_id(prompt)
    if re.search(r"\bstatus\b", prompt, re.I):
        uri = f"agent://{agent_id}/status"
        operation = "read"
    elif re.search(r"\bhealth\b", prompt, re.I):
        uri = resolve_health_uri(prompt)
        operation = "read"
    elif re.search(r"\bcard\b", prompt, re.I):
        uri = resolve_card_uri(prompt)
        operation = "read"
    else:
        uri = f"agent://{agent_id}"
        operation = "read"
    return wrap_nl2uri_output("single_uri", prompt, {"uri": uri, "operation": operation})


def plan_list(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    del use_llm
    uris = [
        {"uri": resolve_health_uri(prompt), "operation": "read"},
        {"uri": resolve_card_uri(prompt), "operation": "read"},
    ]
    if re.search(r"\blog", prompt, re.I):
        uris.append({"uri": resolve_log_uri(prompt), "operation": "read"})
    return wrap_nl2uri_output("uri_list", prompt, {"uris": uris})


def plan_tree(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    tree_data = plan_from_prompt(prompt, use_llm=use_llm)
    children: list[str] = []
    for group in ("inputs", "commands", "resources", "artifacts"):
        for item in (tree_data.get(group) or {}).values():
            uri = item.get("uri") or item.get("uri_template")
            if uri:
                children.append(uri)
    agent = tree_data.get("agent") or {}
    if agent.get("uri"):
        children.append(agent["uri"])
    if agent.get("card_uri"):
        children.append(agent["card_uri"])
    return wrap_nl2uri_output(
        "resource_tree",
        prompt,
        {
            "tree": {
                "root": tree_data.get("domain", {}).get("uri"),
                "children": children,
            },
            "uri_tree": tree_data,
        },
    )


def _extract_site_urls(prompt: str) -> list[str]:
    urls = re.findall(r"https?://[^\s,]+", prompt, re.I)
    if urls:
        return [url.rstrip(".,)") for url in urls]
    domains = re.findall(
        r"\b(?:www\.)?([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\b",
        prompt,
        re.I,
    )
    seen: set[str] = set()
    sites: list[str] = []
    for domain in domains:
        key = domain.lower()
        if key in seen:
            continue
        seen.add(key)
        sites.append(f"https://{domain.lower()}")
    return sites or list(DEFAULT_SCREENSHOT_SITES)


def _extract_interval_minutes(prompt: str) -> int | None:
    match = re.search(r"co\s+(\d+)\s*minut", prompt, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"every\s+(\d+)\s*min(?:ute)?s?", prompt, re.I)
    if match:
        return int(match.group(1))
    return None


def _extract_output_dir(prompt: str) -> str:
    match = re.search(r"(~/[^\s,]+)", prompt)
    if match:
        return match.group(1)
    return "~/images/"


def plan_screenshot_schedule(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    del use_llm
    text = prompt.strip()
    sites = _extract_site_urls(text)
    interval_minutes = _extract_interval_minutes(text)
    output_dir = _extract_output_dir(text)
    steps: list[dict[str, Any]] = []
    previous_step: str | None = None
    for index, site in enumerate(sites):
        slug = _slug(site.replace("https://", "").replace("http://", ""))
        open_id = f"open_{slug or index}"
        capture_id = f"screenshot_{slug or index}"
        open_step: dict[str, Any] = {
            "id": open_id,
            "uri": "browser://chrome/page/open",
            "operation": "open",
            "kind": "command",
            "payload": {"url": site},
        }
        if previous_step:
            open_step["depends_on"] = [previous_step]
        steps.append(open_step)
        steps.append(
            {
                "id": capture_id,
                "uri": "screen://browser/active/screenshot",
                "operation": "capture",
                "kind": "query",
                "depends_on": [open_id],
                "produces": [f"artifact://operator/screenshots/{slug or index}.png"],
            }
        )
        previous_step = capture_id
    return wrap_nl2uri_output(
        "task_graph",
        prompt,
        {
            "flow": {
                "id": WEBSITE_SCREENSHOT_SCHEDULE_ID,
                "description": text,
                "schedule_minutes": interval_minutes,
                "output_dir": output_dir,
                "sites": sites,
            },
            "task": {
                "id": WEBSITE_SCREENSHOT_SCHEDULE_ID,
                "description": text,
            },
            "steps": steps,
        },
    )


def plan_task(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    if use_llm:
        from nl2uri.graph_planner_llm import plan_graph_with_llm

        return plan_graph_with_llm(prompt, kind="task_graph")
    health_uri = resolve_health_uri(prompt)
    task_id = _slug(prompt[:80])
    steps = [
        {
            "id": "open_health",
            "uri": "browser://chrome/page/open",
            "operation": "open",
            "kind": "command",
            "payload": {"url": health_uri},
        },
        {
            "id": "extract_body",
            "uri": "dom://chrome/active/body",
            "operation": "read",
            "kind": "query",
            "depends_on": ["open_health"],
        },
        {
            "id": "verify_ok",
            "uri": "assertion://contains",
            "operation": "check",
            "kind": "assertion",
            "payload": {"actual_from": "extract_body.text", "expected": "ok"},
            "depends_on": ["extract_body"],
        },
    ]
    if re.search(r"screenshot", prompt, re.I):
        steps.append(
            {
                "id": "capture_screenshot",
                "uri": "screen://browser/active/screenshot",
                "operation": "capture",
                "kind": "query",
                "depends_on": ["verify_ok"],
                "produces": ["artifact://operator/screenshots/health-check.png"],
            }
        )
    return wrap_nl2uri_output(
        "task_graph",
        prompt,
        {
            "task": {
                "id": task_id,
                "description": prompt.strip(),
            },
            "steps": steps,
        },
    )


def plan_workflow_graph(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    if use_llm:
        from nl2uri.graph_planner_llm import plan_graph_with_llm

        return plan_graph_with_llm(prompt, kind="workflow_graph")
    text = prompt.strip()
    graph_id = _slug(text[:80])
    nodes: list[dict[str, Any]] = []
    agent_id = resolve_agent_id(text)
    deployment_id = resolve_deployment_id(text)
    domain_uri = resolve_domain_uri(text)

    if re.search(r"\b(wygeneruj|generuj|stw[oó]rz)\b", text, re.I):
        nodes.extend(
            [
                {
                    "id": "generate_domain",
                    "type": "domain_pack",
                    "uri": domain_uri,
                    "operation": "generate",
                    "kind": "command",
                },
                {
                    "id": "generate_agent",
                    "type": "agent",
                    "uri": f"agent://{agent_id}",
                    "operation": "generate",
                    "kind": "command",
                    "depends_on": ["generate_domain"],
                },
            ]
        )

    if re.search(r"\b(uruchom|run)\b", text, re.I):
        nodes.append(
            {
                "id": "run_agent",
                "type": "deployment",
                "uri": f"hypervisor://deployment/{deployment_id}/run",
                "operation": "run",
                "kind": "command",
                "depends_on": [nodes[-1]["id"]] if nodes else [],
            }
        )

    health_uri = resolve_health_uri(text)
    browser_dep = [nodes[-1]["id"]] if nodes else []
    nodes.extend(
        [
            {
                "id": "open_health",
                "type": "browser",
                "uri": "browser://chrome/page/open",
                "operation": "open",
                "kind": "command",
                "payload": {"url": health_uri},
                **({"depends_on": browser_dep} if browser_dep else {}),
            },
            {
                "id": "read_health_dom",
                "type": "browser",
                "uri": "dom://chrome/active/body",
                "operation": "read",
                "kind": "query",
                "depends_on": ["open_health"],
            },
            {
                "id": "verify_ok",
                "type": "assertion",
                "uri": "assertion://contains",
                "operation": "check",
                "kind": "assertion",
                "depends_on": ["read_health_dom"],
                "payload": {"actual_from": "read_health_dom.text", "expected": "ok"},
            },
        ]
    )

    if re.search(r"\b(restart|zrestartuj|nie dzia[lł]a)\b", text, re.I):
        nodes.extend(
            [
                {
                    "id": "health",
                    "uri": health_uri,
                    "operation": "query",
                    "kind": "query",
                    "depends_on": browser_dep or [],
                },
                {
                    "id": "card",
                    "uri": resolve_card_uri(text),
                    "operation": "query",
                    "kind": "query",
                    "depends_on": browser_dep or [],
                },
                {
                    "id": "logs",
                    "uri": resolve_log_uri(text),
                    "operation": "query",
                    "kind": "query",
                    "depends_on": ["health"],
                },
                {
                    "id": "restart",
                    "uri": f"hypervisor://deployment/{deployment_id}/restart",
                    "operation": "command",
                    "kind": "command",
                    "depends_on": ["health"],
                    "condition": {"if": "health.ok == false"},
                },
            ]
        )
    elif re.search(r"\blog", text, re.I):
        nodes.append(
            {
                "id": "read_logs_if_failed",
                "type": "log",
                "uri": resolve_log_uri(text),
                "operation": "read",
                "kind": "query",
                "depends_on": ["verify_ok"],
                "condition": {"if": "verify_ok.ok == false"},
            }
        )

    if not nodes:
        return plan_task(prompt, use_llm=use_llm)

    return wrap_nl2uri_output(
        "workflow_graph",
        prompt,
        {
            "graph": {
                "id": graph_id,
                "version": 1,
                "kind": "workflow",
                "description": text,
                "nodes": nodes,
            }
        },
    )


def plan_auto(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    kind = classify_output_kind(prompt)
    return plan_by_kind(prompt, kind=kind, use_llm=use_llm)


def plan_by_kind(prompt: str, *, kind: str, use_llm: bool = False) -> dict[str, Any]:
    if kind == "uri_flow":
        from nl2uri.flow_planner import plan_flow

        return plan_flow(prompt, use_llm=use_llm)
    planners = {
        "single_uri": plan_single,
        "uri_list": plan_list,
        "resource_tree": plan_tree,
        "task_graph": plan_task,
        "workflow_graph": plan_workflow_graph,
    }
    planner = planners.get(kind, plan_single)
    return planner(prompt, use_llm=use_llm)

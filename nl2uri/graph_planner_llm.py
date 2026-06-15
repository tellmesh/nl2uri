from __future__ import annotations

import json
import os
from typing import Any

import httpx

from nl2uri.graph_repair import repair_and_validate_graph
from nl2uri.planner_llm import extract_json
from uri3.graph.operation_registry import operation_registry_summary


def build_graph_planner_system_prompt(*, kind: str) -> str:
    registry = operation_registry_summary()
    allowed_schemes = ", ".join(sorted(registry))
    task_example = {
        "task": {"id": "health-check", "description": "Open health page and verify ok"},
        "steps": [
            {
                "id": "open_health",
                "uri": "browser://chrome/page/open",
                "operation": "open",
                "kind": "command",
                "payload": {"url": "http://localhost:<port>/health"},
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
        ],
    }
    workflow_example = {
        "graph": {
            "id": "<domain>-health",
            "version": 1,
            "kind": "workflow",
            "description": "Generate <domain> agent, run it, verify health in browser",
            "nodes": [
                {
                    "id": "generate_domain",
                    "uri": "domain://<domain>",
                    "operation": "generate",
                    "kind": "command",
                },
                {
                    "id": "run_agent",
                    "uri": "hypervisor://deployment/<agent-id>.local/run",
                    "operation": "run",
                    "kind": "command",
                    "depends_on": ["generate_domain"],
                },
                {
                    "id": "open_health",
                    "uri": "browser://chrome/page/open",
                    "operation": "open",
                    "kind": "command",
                    "payload": {"url": "http://localhost:<port>/health"},
                    "depends_on": ["run_agent"],
                },
            ],
        }
    }
    shape = task_example if kind == "task_graph" else workflow_example
    return f"""You generate strict JSON workflow plans for the uri3 graph executor.
Return ONLY JSON (no markdown, no commentary).

Allowed schemes: {allowed_schemes}
Do NOT invent handlers, adapters, or URI schemes outside this registry:
{json.dumps(registry, indent=2, ensure_ascii=False)}

Rules:
- Every node/step MUST include id, uri, operation.
- uri scheme MUST be one of the allowed schemes above.
- operation MUST be one of the allowed operations for that scheme.
- Use depends_on for ordering; do not create cycles.
- command kind steps require human approval at execution time.
- Do not use handler_uri, mcp://, python://, or other unsupported schemes.

Return JSON in this shape for kind={kind}:
{json.dumps(shape, indent=2, ensure_ascii=False)}"""


def call_graph_planner_llm(
    prompt: str,
    *,
    kind: str,
    profile_name: str | None = None,
) -> dict[str, Any]:
    from uri3.config.llm_profiles import resolve_llm_profile

    profile = resolve_llm_profile(profile_name or os.getenv("DEFAULT_LLM_PROFILE", "graph_planner"))
    if not profile.api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    system = build_graph_planner_system_prompt(kind=kind)
    payload: dict[str, Any] = {
        "model": profile.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
    }
    if profile.response_format == "json":
        payload["response_format"] = {"type": "json_object"}
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{profile.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {profile.api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    return extract_json(content)


def plan_graph_with_llm(prompt: str, *, kind: str, profile_name: str | None = None) -> dict[str, Any]:
    from nl2uri.graph_planner import plan_task, plan_workflow_graph, wrap_nl2uri_output

    fallback = plan_task if kind == "task_graph" else plan_workflow_graph
    try:
        raw = call_graph_planner_llm(prompt, kind=kind, profile_name=profile_name)
        wrapper = wrap_nl2uri_output(kind, prompt, {})
        body, repair_warnings = repair_and_validate_graph(
            raw,
            prompt,
            kind=kind,
            nl2uri_wrapper=wrapper,
        )
        result = wrap_nl2uri_output(kind, prompt, body)
        warnings = list(repair_warnings)
        if warnings:
            result["planner_warning"] = "; ".join(warnings)
        return result
    except Exception as exc:
        result = fallback(prompt, use_llm=False)
        result["planner_warning"] = f"LLM graph planner failed, rule-based fallback used: {exc}"
        return result

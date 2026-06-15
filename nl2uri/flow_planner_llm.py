from __future__ import annotations

import json
import os
from typing import Any

import httpx

from nl2uri.flow_repair import repair_and_validate_flow
from nl2uri.planner_llm import extract_json
from uri3.graph.operation_registry import operation_registry_summary


def build_flow_planner_system_prompt() -> str:
    registry = operation_registry_summary()
    allowed_schemes = ", ".join(sorted(registry))
    example = {
        "flow": {
            "id": "<domain>-agent-health",
            "description": "Generate <domain> agent, run locally, verify health in Chrome",
        },
        "do": [
            "agent://<domain>-generator",
            "hypervisor://local/<agent-id>/run",
            {
                "uri": "browser://chrome/page/open",
                "with": {"url": "http://localhost:<port>/health"},
            },
        ],
    }
    branching_example = {
        "flow": {"id": "check-agent"},
        "do": [
            {"id": "run_agent", "uri": "hypervisor://local/<agent-id>/run"},
            {"id": "health", "uri": "http://localhost:<port>/health", "after": "run_agent"},
            {
                "id": "logs_if_failed",
                "uri": "log://<agent-id>?limit=100",
                "after": "health",
                "if": "health.ok == false",
            },
        ],
    }
    return f"""You generate strict JSON compact URI flows for uri2flow/uri3.
Return ONLY JSON (no markdown, no commentary).

Allowed schemes: {allowed_schemes}
Do NOT invent unsupported URI schemes or python:// handlers.
Operation/kind are inferred from config/flow_defaults.uri.yaml — omit them unless overriding.

Rules:
- Return compact flow with top-level keys: flow, do
- flow.id must be a short slug
- do is an ordered list of URI strings or step objects
- Step object shape: {{"id": "...", "uri": "...", "with": {{...}}, "after": "...", "if": "..."}}
- Compact URI mapping is allowed: {{"browser://chrome/page/open": {{"url": "..."}}}}
- Use after for dependencies; use if for conditional steps
- Prefer sequential compact URIs over full workflow graphs
- Do not return graph.nodes or task.steps unless converting to do

Example linear flow:
{json.dumps(example, indent=2, ensure_ascii=False)}

Example branching flow:
{json.dumps(branching_example, indent=2, ensure_ascii=False)}

Registry summary:
{json.dumps(registry, indent=2, ensure_ascii=False)}"""


def call_flow_planner_llm(prompt: str, *, profile_name: str | None = None) -> dict[str, Any]:
    from uri3.config.llm_profiles import resolve_llm_profile

    profile = resolve_llm_profile(profile_name or os.getenv("DEFAULT_LLM_PROFILE", "flow_planner"))
    if not profile.api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    system = build_flow_planner_system_prompt()
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


def plan_flow_with_llm(prompt: str, *, profile_name: str | None = None) -> dict[str, Any]:
    from nl2uri.flow_planner import plan_flow
    from nl2uri.graph_planner import wrap_nl2uri_output

    try:
        raw = call_flow_planner_llm(prompt, profile_name=profile_name)
        wrapper = wrap_nl2uri_output("uri_flow", prompt, {})
        body, repair_warnings = repair_and_validate_flow(raw, prompt, nl2uri_wrapper=wrapper)
        result = wrap_nl2uri_output("uri_flow", prompt, body)
        if repair_warnings:
            result["planner_warning"] = "; ".join(repair_warnings)
        return result
    except Exception as exc:
        result = plan_flow(prompt, use_llm=False)
        result["planner_warning"] = f"LLM flow planner failed, rule-based fallback used: {exc}"
        return result

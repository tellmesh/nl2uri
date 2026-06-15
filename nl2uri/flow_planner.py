from __future__ import annotations

import re
from typing import Any

from nl2uri.agent_resolution import (
    resolve_agent_id,
    resolve_card_uri,
    resolve_generator_alias,
    resolve_health_uri,
    resolve_local_run_slug,
    resolve_log_uri,
)
from nl2uri.graph_planner import _slug, wrap_nl2uri_output


def _compact_step(uri: str, payload: dict[str, Any] | None = None) -> str | dict[str, Any]:
    if payload:
        return {uri: payload}
    return uri


def plan_flow(prompt: str, *, use_llm: bool = False) -> dict[str, Any]:
    """Plan a compact URI flow (human/LLM input format)."""
    if use_llm:
        from nl2uri.flow_planner_llm import plan_flow_with_llm

        return plan_flow_with_llm(prompt)

    text = prompt.strip()
    flow_id = _slug(text[:80])
    steps: list[str | dict[str, Any]] = []

    if re.search(r"\b(wygeneruj|generuj|stw[oó]rz|zbuduj)\b", text, re.I):
        steps.append(f"agent://{resolve_generator_alias(text)}")

    if re.search(r"\b(uruchom|run)\b", text, re.I):
        steps.append(f"hypervisor://local/{resolve_local_run_slug(text)}/run")

    health_uri = resolve_health_uri(text)
    if re.search(r"\b(chrome|przegl[aą]dark|browser|sprawd[zź]|health|localhost)\b", text, re.I):
        steps.append(_compact_step("browser://chrome/page/open", {"url": health_uri}))

    if re.search(r"\b(agent card|karta agenta)\b", text, re.I):
        card_uri = resolve_card_uri(text)
        if steps:
            steps.append({"id": "read_card", "uri": card_uri, "after": _last_step_id(steps, fallback="run_agent")})
        else:
            steps.append(card_uri)

    if re.search(r"\b(je[sś]li|if|gdy).*(log|nie dzia)", text, re.I | re.S):
        local_slug = resolve_local_run_slug(text)
        steps.extend(
            [
                {"id": "run_agent", "uri": f"hypervisor://local/{local_slug}/run"},
                {"id": "check_health", "uri": health_uri, "after": "run_agent"},
                {
                    "id": "logs_if_failed",
                    "uri": resolve_log_uri(text),
                    "after": "check_health",
                    "if": "check_health.ok == false",
                },
            ]
        )

    if not steps:
        if re.search(r"\b(otw[oó]rz|open)\b", text, re.I):
            steps.append(_compact_step("browser://chrome/page/open", {"url": health_uri}))
        elif re.search(r"\bhealth\b", text, re.I):
            steps.append(health_uri)
        else:
            steps.append(f"agent://{resolve_agent_id(text)}")

    return wrap_nl2uri_output(
        "uri_flow",
        prompt,
        {
            "flow": {"id": flow_id, "description": text},
            "do": steps,
        },
    )


def _last_step_id(steps: list[str | dict[str, Any]], *, fallback: str) -> str:
    for item in reversed(steps):
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    return fallback

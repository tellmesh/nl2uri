from __future__ import annotations

import os
from typing import Any

from nl2uri.domain_registry import resolve_plan
from nl2uri.planner_llm import call_openrouter
from nl2uri.planner_validation import normalize_llm_tree

_normalize_llm_tree = normalize_llm_tree


def plan_from_prompt(prompt: str, use_llm: bool | None = None) -> dict[str, Any]:
    if use_llm is None:
        use_llm = os.getenv("NL2A_USE_LLM", "0") in {"1", "true", "TRUE", "yes"}
    if use_llm:
        try:
            llm_tree = call_openrouter(prompt)
            if not isinstance(llm_tree, dict):
                raise ValueError("LLM planner did not return a JSON object")
            return normalize_llm_tree(prompt, llm_tree)
        except Exception as exc:
            plan = resolve_plan(prompt)
            plan["planner_warning"] = f"LLM planner failed, deterministic fallback used: {exc}"
            return plan
    return resolve_plan(prompt)


plan_domain_from_prompt = plan_from_prompt

__all__ = ["_normalize_llm_tree", "plan_domain_from_prompt", "plan_from_prompt"]

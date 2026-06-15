from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
import yaml


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return yaml.safe_load(text)


def call_openrouter(prompt: str, *, profile_name: str | None = None) -> dict[str, Any]:
    from uri3.config.llm_profiles import resolve_llm_profile

    profile = resolve_llm_profile(profile_name or os.getenv("DEFAULT_LLM_PROFILE", "domain_planner"))
    if not profile.api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    system = """You generate a strict JSON URI Tree for a contract-first agent hypervisor.
Return only JSON (no markdown).
Top-level keys MUST be objects, not arrays:
domain {id, uri, name, description}
inputs { ... }
commands { key: {uri, name, handler_uri, ...} }
events { ... }
resources { key: {uri_template, schema_ref, ...} }
artifacts { ... }
agent {id, uri, card_uri, capabilities: [...]}
deployment {default: {uri: ...}}
mcp { ... }
dependencies [pypi://...]
Never return commands/resources/agent as bare URI strings or YAML lists."""
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

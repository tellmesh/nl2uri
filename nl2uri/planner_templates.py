from __future__ import annotations

import os
import re
from typing import Any

DEFAULT_MODEL_URI = "llm://openrouter/qwen/qwen3-coder-next"


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "generated-domain"


def llm_uri_from_env() -> str:
    from uri3.config.llm_profiles import resolve_llm_profile

    profile_name = os.getenv("DEFAULT_LLM_PROFILE", "domain_planner")
    try:
        return resolve_llm_profile(profile_name, resolve_secrets=False).model_uri
    except Exception:
        raw = os.getenv("DOMAIN_PLANNER_LLM") or os.getenv("LLM_MODEL")
        if not raw:
            return DEFAULT_MODEL_URI
        if raw.startswith("llm://"):
            return raw
        if raw.startswith("openrouter/"):
            return raw.replace("openrouter/", "llm://openrouter/", 1)
        return f"llm://{raw}"



def generic_plan(prompt: str) -> dict[str, Any]:
    slug_value = slug(prompt[:80])
    domain_id = slug_value.replace("-", "_")
    agent_id = f"{slug_value}-agent"
    return {
        "domain": {"id": domain_id, "uri": f"domain://{slug_value}", "name": slug_value, "description": prompt},
        "standards": {"uri_tree_schema": "schemas/uri_tree.schema.json", "data_contract": "protobuf", "agent_manifest": "a2a_agent_card", "resource_model": "mcp_resources"},
        "inputs": {"input": {"uri": f"input://{slug_value}/input", "type": "string", "required": True}},
        "commands": {"run": {"uri": f"command://{slug_value}/run", "name": "RunTask", "handler_uri": f"python://domains.{domain_id}.handlers.run:handler", "input_schema_ref": f"app.{domain_id}.v1.RunTaskCommand", "emits": [f"event://{slug_value}/TaskRequested", f"event://{slug_value}/TaskCompleted"]}},
        "events": {"requested": {"uri": f"event://{slug_value}/TaskRequested", "name": "TaskRequested", "schema_ref": f"app.{domain_id}.v1.TaskRequested"}, "completed": {"uri": f"event://{slug_value}/TaskCompleted", "name": "TaskCompleted", "schema_ref": f"app.{domain_id}.v1.TaskCompleted"}},
        "resources": {"result": {"uri_template": f"resource://{slug_value}/result/{{id}}", "schema_ref": f"app.{domain_id}.v1.TaskResultView", "renderer_ref": "json", "mime_type": "application/json"}},
        "artifacts": {},
        "agent": {"id": agent_id, "uri": f"agent://{agent_id}", "name": agent_id, "card_uri": f"a2a://{agent_id}/.well-known/agent-card.json", "capabilities": [{"name": "run", "type": "command", "uri": f"a2a://{agent_id}/skills/run"}]},
        "deployment": {"default": {"uri": f"local://agents/generated/{agent_id.replace('-', '_')}"}},
        "mcp": {"resources_read": {"uri": f"mcp://{agent_id}/resources/read"}},
        "dependencies": ["pypi://pydantic"],
    }

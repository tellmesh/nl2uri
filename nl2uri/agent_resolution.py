from __future__ import annotations

import re
from typing import Any

from hypervisor.deployment_registry.selector import resolve_deployment

from nl2uri.domain_registry import match_domain, repo_root, resolve_plan
from nl2uri.planner_templates import slug

DEFAULT_HEALTH = "http://localhost:8000/health"
DEFAULT_CARD = "http://localhost:8000/.well-known/agent-card.json"


def _agent_id_from_plan(plan: dict[str, Any]) -> str:
    agent = plan.get("agent") or {}
    if agent.get("id"):
        return str(agent["id"])
    domain = plan.get("domain") or {}
    domain_name = str(domain.get("name") or domain.get("id") or "generated-agent")
    return f"{slug(domain_name.replace('_', '-'))}-agent"


def _domain_slug(prompt: str) -> str:
    domain = resolve_plan(prompt).get("domain") or {}
    name = domain.get("name") or domain.get("id") or slug(prompt[:80])
    return slug(str(name).replace("_", "-"))


def resolve_agent_id(prompt: str) -> str:
    entry = match_domain(prompt)
    if entry is not None:
        agent = entry.deterministic_plan(prompt).get("agent") or {}
        if agent.get("id"):
            return str(agent["id"])
    match = re.search(r"\bagent:\s*([a-z0-9-]+)", prompt, re.I)
    if match:
        return match.group(1)
    match = re.search(r"\bagent\s+([a-z0-9]+(?:-[a-z0-9-]+)+)\b", prompt, re.I)
    if match:
        return match.group(1)
    return _agent_id_from_plan(resolve_plan(prompt))


def resolve_domain_uri(prompt: str) -> str:
    domain = resolve_plan(prompt).get("domain") or {}
    return str(domain.get("uri") or f"domain://{_domain_slug(prompt)}")


def resolve_deployment_id(prompt: str, *, prefer_local: bool = True) -> str:
    entry = match_domain(prompt)
    if entry and entry.default_deployment_id:
        return entry.default_deployment_id
    agent_id = resolve_agent_id(prompt)
    candidate = f"{agent_id}.local"
    try:
        deployment = resolve_deployment(candidate, root=repo_root(), prefer_local=prefer_local)
        return deployment.id
    except ValueError:
        return candidate


def resolve_generator_alias(prompt: str) -> str:
    entry = match_domain(prompt)
    if entry:
        alias = entry.flow_aliases.get("generator")
        if alias:
            return str(alias)
    return f"{_domain_slug(prompt)}-generator"


def resolve_local_run_slug(prompt: str) -> str:
    entry = match_domain(prompt)
    if entry:
        alias = entry.flow_aliases.get("local_run")
        if alias:
            return str(alias)
        if entry.deployment_selector_aliases:
            return next(iter(entry.deployment_selector_aliases))
    match = re.search(r"\bagent:\s*([a-z0-9-]+)", prompt, re.I)
    if match:
        return match.group(1)
    match = re.search(r"\bagent\s+([a-z0-9]+(?:-[a-z0-9-]+)+)\b", prompt, re.I)
    if match:
        return match.group(1)
    base = _domain_slug(prompt)
    return f"{base}-agent" if base else "generated-agent"


def resolve_health_uri(prompt: str) -> str:
    match = re.search(r"https?://[^\s,]+", prompt)
    if match:
        return match.group(0).rstrip(".,)")
    port_match = re.search(r"localhost:(\d+)", prompt, re.I)
    if port_match:
        return f"http://localhost:{port_match.group(1)}/health"
    entry = match_domain(prompt)
    if entry and entry.default_health_uri:
        return entry.default_health_uri
    try:
        deployment = resolve_deployment(resolve_deployment_id(prompt), root=repo_root())
        if deployment.health_uri:
            return str(deployment.health_uri)
    except ValueError:
        pass
    return DEFAULT_HEALTH


def resolve_card_uri(prompt: str) -> str:
    entry = match_domain(prompt)
    if entry and entry.default_card_uri:
        return entry.default_card_uri
    health_uri = resolve_health_uri(prompt)
    if health_uri.endswith("/health"):
        return health_uri[: -len("/health")] + "/.well-known/agent-card.json"
    return DEFAULT_CARD


def resolve_log_uri(prompt: str, *, limit: int = 100) -> str:
    return f"log://{resolve_deployment_id(prompt)}?limit={limit}"

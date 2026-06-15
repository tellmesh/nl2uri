from __future__ import annotations

import re
from typing import Any

from uri3.graph.graph_serializer import normalize_graph_payload, task_steps_to_graph
from uri3.graph.graph_validator import validate_workflow_graph
from uri3.graph.operation_registry import (
    DEFAULT_KIND_BY_SCHEME,
    OPERATIONS_BY_SCHEME,
    allowed_operations,
    scheme_from_uri,
    validate_node_operation,
)

OPERATION_ALIASES: dict[str, dict[str, str]] = {
    "browser": {"open_page": "open", "navigate": "open", "goto": "open", "screenshot": "capture"},
    "dom": {"get": "read", "extract_text": "read", "text": "read"},
    "screen": {"screenshot": "capture", "shot": "capture"},
    "assertion": {"contains": "check", "equals": "check", "match": "check", "verify": "check"},
    "hypervisor": {"command": "run", "deploy": "run", "start": "run", "stop": "restart"},
    "http": {"get": "read", "fetch": "read"},
    "https": {"get": "read", "fetch": "read"},
    "log": {"fetch": "read", "tail": "read"},
    "agent": {"query": "read", "info": "status"},
    "domain": {"create": "generate", "build": "generate"},
}


def _slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "task"


def _coerce_operation(scheme: str, operation: str) -> str:
    normalized = str(operation).strip().lower()
    aliases = OPERATION_ALIASES.get(scheme, {})
    if normalized in aliases:
        normalized = aliases[normalized]
    allowed = allowed_operations(scheme)
    if normalized in allowed:
        return normalized
    for candidate in ("read", "query", "check", "open", "run", "capture", "generate"):
        if candidate in allowed:
            return candidate
    return sorted(allowed)[0]


def extract_graph_payload(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("LLM graph planner did not return a JSON object")
    body = _without_nl2uri_wrapper(raw)
    for extractor in (
        _extract_graph_block,
        _extract_task_steps_block,
        _extract_raw_nodes_block,
        _extract_steps_block,
    ):
        payload = extractor(body)
        if payload is not None:
            return payload
    raise ValueError("LLM response missing graph or task/steps")


def _without_nl2uri_wrapper(raw: dict[str, Any]) -> dict[str, Any]:
    if "nl2uri" in raw and isinstance(raw["nl2uri"], dict):
        return {key: value for key, value in raw.items() if key != "nl2uri"}
    return raw


def _extract_graph_block(raw: dict[str, Any]) -> dict[str, Any] | None:
    if "graph" in raw and isinstance(raw["graph"], dict):
        return {"graph": raw["graph"]}
    return None


def _extract_task_steps_block(raw: dict[str, Any]) -> dict[str, Any] | None:
    if "task" in raw and "steps" in raw:
        return {"task": raw["task"], "steps": raw["steps"]}
    return None


def _extract_raw_nodes_block(raw: dict[str, Any]) -> dict[str, Any] | None:
    if "nodes" in raw:
        return {"graph": raw}
    return None


def _extract_steps_block(raw: dict[str, Any]) -> dict[str, Any] | None:
    if "steps" not in raw or not isinstance(raw["steps"], list):
        return None
    task = raw.get("task") if isinstance(raw.get("task"), dict) else {"id": "task"}
    return {"task": task, "steps": raw["steps"]}


def normalize_to_kind(body: dict[str, Any], *, kind: str, prompt: str) -> dict[str, Any]:
    if kind == "workflow_graph" and "task" in body and "steps" in body:
        return _task_steps_to_workflow_graph(body, prompt)
    if kind == "task_graph" and "graph" in body:
        return _graph_to_task_steps(body["graph"], prompt)
    return body


def _task_steps_to_workflow_graph(body: dict[str, Any], prompt: str) -> dict[str, Any]:
    graph = task_steps_to_graph(body["task"], body["steps"])
    graph.kind = "workflow"
    if not graph.description:
        graph.description = prompt.strip()
    return {"graph": graph.to_dict()}


def _graph_to_task_steps(graph_data: dict[str, Any], prompt: str) -> dict[str, Any]:
    task = {
        "id": str(graph_data.get("id") or _slug(prompt[:80])),
        "description": str(graph_data.get("description") or prompt.strip()),
    }
    return {"task": task, "steps": _node_list(graph_data.get("nodes") or [])}


def _optional_node_fields(node: dict[str, Any], sanitized: dict[str, Any]) -> None:
    for field in ("type", "condition"):
        if node.get(field):
            sanitized[field] = node[field]
    for field in ("produces", "emits"):
        if node.get(field):
            sanitized[field] = list(node[field])
    if node.get("depends_on"):
        sanitized["depends_on"] = [str(item) for item in node["depends_on"]]


def _node_identity(
    node: dict[str, Any],
    *,
    warnings: list[str],
) -> tuple[str, str] | None:
    node_id = str(node.get("id") or "").strip()
    uri = str(node.get("uri") or "").strip()
    if not node_id or not uri:
        warnings.append(f"dropped node with missing id or uri: {node!r}")
        return None
    return node_id, uri


def _node_scheme(node_id: str, uri: str, *, warnings: list[str]) -> str | None:
    scheme = scheme_from_uri(uri)
    if scheme not in OPERATIONS_BY_SCHEME:
        warnings.append(f"dropped node {node_id!r}: unsupported scheme {scheme!r}")
        return None
    return scheme


def _build_sanitized_node(
    node: dict[str, Any],
    *,
    node_id: str,
    uri: str,
    scheme: str,
) -> dict[str, Any]:
    operation = _coerce_operation(scheme, str(node.get("operation") or "read"))
    kind = node.get("kind") or DEFAULT_KIND_BY_SCHEME.get(scheme, "query")
    sanitized: dict[str, Any] = {
        "id": node_id,
        "uri": uri,
        "operation": operation,
        "kind": kind,
    }
    if isinstance(node.get("payload"), dict) and node["payload"]:
        sanitized["payload"] = dict(node["payload"])
    _optional_node_fields(node, sanitized)
    return sanitized


def sanitize_node(node: dict[str, Any], *, warnings: list[str]) -> dict[str, Any] | None:
    identity = _node_identity(node, warnings=warnings)
    if identity is None:
        return None
    node_id, uri = identity
    scheme = _node_scheme(node_id, uri, warnings=warnings)
    if scheme is None:
        return None
    return _build_sanitized_node(node, node_id=node_id, uri=uri, scheme=scheme)


def _sanitize_nodes(nodes: list[dict[str, Any]], *, warnings: list[str]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for node in nodes:
        item = sanitize_node(node, warnings=warnings)
        if item:
            sanitized.append(item)
    _prune_unknown_dependencies(sanitized, warnings=warnings)
    return sanitized


def _prune_unknown_dependencies(
    nodes: list[dict[str, Any]],
    *,
    warnings: list[str],
) -> None:
    node_ids = {node["id"] for node in nodes}
    for node in nodes:
        _prune_node_dependencies(node, node_ids, warnings=warnings)


def _prune_node_dependencies(
    node: dict[str, Any],
    node_ids: set[str],
    *,
    warnings: list[str],
) -> None:
    deps = [dep for dep in node.get("depends_on") or [] if dep in node_ids]
    dropped = set(node.get("depends_on") or []) - set(deps)
    if dropped:
        warnings.append(f"{node['id']}: removed unknown depends_on {sorted(dropped)!r}")
    if deps:
        node["depends_on"] = deps
    else:
        node.pop("depends_on", None)


def _node_list(nodes: Any) -> list[dict[str, Any]]:
    if isinstance(nodes, dict):
        return [dict(value, id=node_id) for node_id, value in nodes.items()]
    return list(nodes)


def _repair_graph_payload(
    graph_data: dict[str, Any],
    *,
    prompt: str,
    kind: str,
    warnings: list[str],
) -> dict[str, Any]:
    graph_data = dict(graph_data)
    graph_data["nodes"] = _sanitize_nodes(
        _node_list(graph_data.get("nodes") or []), warnings=warnings
    )
    if not graph_data["nodes"]:
        raise ValueError("no valid nodes remain after repair")
    graph_data.setdefault("id", _slug(prompt[:80]))
    graph_data.setdefault("version", 1)
    graph_data.setdefault("kind", "workflow" if kind == "workflow_graph" else "task")
    graph_data.setdefault("description", prompt.strip())
    return {"graph": graph_data}


def _repair_task_steps_payload(
    body: dict[str, Any],
    *,
    prompt: str,
    warnings: list[str],
) -> dict[str, Any]:
    task = dict(body["task"] or {})
    task.setdefault("id", _slug(prompt[:80]))
    task.setdefault("description", prompt.strip())
    steps = _sanitize_nodes(list(body["steps"] or []), warnings=warnings)
    if not steps:
        raise ValueError("no valid steps remain after repair")
    return {"task": task, "steps": steps}


def repair_graph_body(
    raw: dict[str, Any], prompt: str, *, kind: str
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    body = normalize_to_kind(extract_graph_payload(raw), kind=kind, prompt=prompt)
    if "graph" in body:
        return _repair_graph_payload(
            body["graph"], prompt=prompt, kind=kind, warnings=warnings
        ), warnings
    if "task" in body and "steps" in body:
        return _repair_task_steps_payload(body, prompt=prompt, warnings=warnings), warnings
    raise ValueError("repaired body must contain graph or task/steps")


def repair_and_validate_graph(
    raw: dict[str, Any],
    prompt: str,
    *,
    kind: str,
    nl2uri_wrapper: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    body, warnings = repair_graph_body(raw, prompt, kind=kind)
    payload = _wrapped_payload(body, nl2uri_wrapper)
    errors = validate_workflow_graph(payload)
    if _has_operation_errors(errors) and "graph" in body:
        body = _drop_invalid_operation_nodes(body)
        errors = validate_workflow_graph(_wrapped_payload(body, nl2uri_wrapper))
    if errors:
        raise ValueError("; ".join(errors[:5]))
    return body, warnings


def _wrapped_payload(
    body: dict[str, Any],
    nl2uri_wrapper: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(nl2uri_wrapper or {})
    payload.update(body)
    return payload


def _has_operation_errors(errors: list[str]) -> bool:
    return any("operation" in error and "not allowed" in error for error in errors)


def _drop_invalid_operation_nodes(body: dict[str, Any]) -> dict[str, Any]:
    graph_data = dict(body["graph"])
    normalized = normalize_graph_payload(graph_data)
    graph_data["nodes"] = [
        node
        for node in graph_data["nodes"]
        if validate_node_operation(normalized.nodes[node["id"]]) is None
    ]
    return {"graph": graph_data} if graph_data["nodes"] else body

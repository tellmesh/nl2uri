from __future__ import annotations

from typing import Any

from nl2uri.flow_helpers import (
    copy_optional_step_id,
    copy_step_after,
    copy_step_condition,
    copy_step_payload,
)


def _node_to_compact_step(node: dict[str, Any]) -> dict[str, Any]:
    step: dict[str, Any] = {"uri": str(node["uri"])}
    copy_optional_step_id(step, node)
    copy_step_payload(step, node, "payload", "with")
    copy_step_after(step, node, compact_single=True)
    copy_step_condition(step, node)
    return step


def _nodes_to_compact_steps(nodes: list[dict[str, Any]]) -> list[str | dict[str, Any]]:
    return [
        _node_to_compact_step(node) for node in nodes if isinstance(node, dict) and node.get("uri")
    ]


def _normalize_node_list(nodes: Any) -> list[dict[str, Any]]:
    if isinstance(nodes, dict):
        return [dict(value, id=node_id) for node_id, value in nodes.items()]
    return list(nodes)


def _extract_from_flow_do(body: dict[str, Any]) -> dict[str, Any] | None:
    if "flow" in body and "do" in body:
        return {"flow": body["flow"], "do": body["do"]}
    if "do" in body:
        return {"flow": body.get("flow") or {}, "do": body["do"]}
    return None


def _extract_from_steps(body: dict[str, Any]) -> dict[str, Any] | None:
    if "steps" not in body:
        return None
    flow_meta = body.get("flow") if isinstance(body.get("flow"), dict) else {}
    if not flow_meta and isinstance(body.get("task"), dict):
        flow_meta = {
            "id": body["task"].get("id"),
            "description": body["task"].get("description"),
        }
    return {"flow": flow_meta, "do": body["steps"]}


def _extract_from_graph(body: dict[str, Any]) -> dict[str, Any] | None:
    if "graph" in body and isinstance(body["graph"], dict):
        graph = body["graph"]
        return {
            "flow": {"id": graph.get("id"), "description": graph.get("description")},
            "do": _nodes_to_compact_steps(_normalize_node_list(graph.get("nodes") or [])),
        }
    if "nodes" in body:
        return {
            "flow": {"id": body.get("id"), "description": body.get("description")},
            "do": _nodes_to_compact_steps(_normalize_node_list(body["nodes"])),
        }
    return None


def extract_flow_payload(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("LLM flow planner did not return a JSON object")
    body = {key: value for key, value in raw.items() if key != "nl2uri"}
    for extractor in (_extract_from_flow_do, _extract_from_steps, _extract_from_graph):
        payload = extractor(body)
        if payload is not None:
            return payload
    raise ValueError("LLM response missing flow/do, steps, or graph nodes")

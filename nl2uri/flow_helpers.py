from __future__ import annotations

import re
from typing import Any

from uri3.graph.operation_registry import OPERATIONS_BY_SCHEME, scheme_from_uri


def slug_from_prompt(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "flow"


def supported_scheme(uri: str) -> bool:
    scheme = scheme_from_uri(uri)
    return bool(scheme) and scheme in OPERATIONS_BY_SCHEME


def copy_optional_step_id(step: dict[str, Any], source: dict[str, Any]) -> None:
    if source.get("id"):
        step["id"] = str(source["id"])


def payload_from(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        payload = source.get(key)
        if payload:
            return payload
    return {}


def copy_step_payload(step: dict[str, Any], source: dict[str, Any], *keys: str) -> None:
    payload = payload_from(source, *keys)
    if isinstance(payload, dict) and payload:
        step["with"] = dict(payload)


def dependency_value(source: dict[str, Any], *, compact_single: bool) -> Any:
    depends_on = source.get("after") or source.get("depends_on")
    if compact_single and isinstance(depends_on, list) and len(depends_on) == 1:
        return depends_on[0]
    return depends_on


def copy_step_after(
    step: dict[str, Any],
    source: dict[str, Any],
    *,
    compact_single: bool,
) -> None:
    depends_on = dependency_value(source, compact_single=compact_single)
    if depends_on:
        step["after"] = depends_on


def condition_value(source: dict[str, Any]) -> str | None:
    condition = source.get("if") or source.get("condition")
    if isinstance(condition, dict):
        condition = condition.get("if")
    return str(condition) if condition else None


def copy_step_condition(step: dict[str, Any], source: dict[str, Any]) -> None:
    condition = condition_value(source)
    if condition:
        step["if"] = condition


def _normalize_uri_string(raw: str) -> str | None:
    value = raw.strip()
    return value if "://" in value else None


def _normalize_single_uri_mapping(raw: dict[str, Any]) -> str | dict[str, Any] | None:
    uri, payload = next(iter(raw.items()))
    uri = str(uri).strip()
    if "://" not in uri:
        return None
    if payload is None:
        return uri
    if isinstance(payload, dict):
        return {uri: payload}
    return None


def _normalize_step_mapping(raw: dict[str, Any]) -> str | dict[str, Any] | None:
    if "uri" in raw:
        return dict(raw)
    if len(raw) == 1:
        return _normalize_single_uri_mapping(raw)
    if isinstance(raw.get("step"), dict):
        return dict(raw["step"])
    return None


def normalize_step_raw(raw: Any) -> str | dict[str, Any] | None:
    if isinstance(raw, str):
        return _normalize_uri_string(raw)
    if not isinstance(raw, dict):
        return None
    return _normalize_step_mapping(raw)


def build_sanitized_step(normalized: dict[str, Any]) -> dict[str, Any]:
    step: dict[str, Any] = {"uri": str(normalized["uri"]).strip()}
    copy_optional_step_id(step, normalized)
    copy_step_payload(step, normalized, "with", "payload")
    copy_step_after(step, normalized, compact_single=False)
    copy_step_condition(step, normalized)
    return step

from __future__ import annotations

from typing import Any

from uri2flow.utils import slugify

from nl2uri.flow_extract import extract_flow_payload
from nl2uri.flow_helpers import slug_from_prompt
from nl2uri.flow_sanitize import sanitize_flow_step
from nl2uri.flow_step_ids import ensure_step_ids

__all__ = [
    "extract_flow_payload",
    "repair_and_validate_flow",
    "repair_flow_body",
    "sanitize_flow_step",
    "validate_expanded_flow",
    "validate_flow_document",
]


def _flow_metadata(body: dict[str, Any], prompt: str) -> dict[str, Any]:
    flow_meta = dict(body.get("flow") or {})
    if not isinstance(flow_meta, dict):
        flow_meta = {}
    flow_meta.setdefault("id", slugify(str(flow_meta.get("id") or slug_from_prompt(prompt[:80]))))
    flow_meta.setdefault("description", prompt.strip())
    return flow_meta


def _sanitize_flow_steps(body: dict[str, Any], warnings: list[str]) -> list[str | dict[str, Any]]:
    sanitized: list[str | dict[str, Any]] = []
    for index, item in enumerate(body.get("do") or []):
        step = sanitize_flow_step(item, warnings=warnings, index=index)
        if step is not None:
            sanitized.append(step)
    if not sanitized:
        raise ValueError("no valid flow steps remain after repair")
    return sanitized


def repair_flow_body(raw: dict[str, Any], prompt: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    body = extract_flow_payload(raw)
    flow_meta = _flow_metadata(body, prompt)
    sanitized = _sanitize_flow_steps(body, warnings)

    sanitized = ensure_step_ids(sanitized, warnings=warnings)
    return {"flow": flow_meta, "do": sanitized}, warnings


def validate_flow_document(data: dict[str, Any]) -> list[str]:
    from uri2flow.validator import validate_flow_document as _validate

    return _validate(data)


def validate_expanded_flow(data: dict[str, Any]) -> list[str]:
    from uri2flow.validator import validate_expanded_flow as _validate

    return _validate(data)


def repair_and_validate_flow(
    raw: dict[str, Any],
    prompt: str,
    *,
    nl2uri_wrapper: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    body, warnings = repair_flow_body(raw, prompt)
    payload = dict(nl2uri_wrapper or {})
    payload.update(body)
    flow_warnings = validate_expanded_flow(payload)
    return body, warnings + flow_warnings

from __future__ import annotations

from typing import Any

from uri2flow.utils import node_id_from_uri


def needs_explicit_ids(steps: list[str | dict[str, Any]]) -> bool:
    return any(isinstance(step, dict) and (step.get("after") or step.get("if")) for step in steps)


def _after_refs(after: Any) -> list[str]:
    if isinstance(after, str):
        return [after]
    if isinstance(after, list):
        return [str(item) for item in after]
    return []


def _set_after_refs(step: dict[str, Any], refs: list[str]) -> None:
    if refs:
        step["after"] = refs[0] if len(refs) == 1 else refs
    else:
        step.pop("after", None)


def _remove_unknown_after_refs(step: dict[str, Any], known_ids: set[str]) -> list[str]:
    refs = _after_refs(step.get("after"))
    kept = [ref for ref in refs if ref in known_ids]
    _set_after_refs(step, kept)
    return sorted(set(refs) - set(kept))


def _assign_missing_step_ids(
    steps: list[str | dict[str, Any]],
    *,
    warnings: list[str],
) -> list[str | dict[str, Any]]:
    used: set[str] = set()
    normalized: list[str | dict[str, Any]] = []
    for step in steps:
        if isinstance(step, str):
            step_id = node_id_from_uri(step, used)
            normalized.append({"id": step_id, "uri": step})
            continue
        item = dict(step)
        if not item.get("id"):
            item["id"] = node_id_from_uri(str(item["uri"]), used)
            warnings.append(f"assigned id {item['id']!r} to step {item['uri']!r}")
        else:
            used.add(str(item["id"]))
        normalized.append(item)
    return normalized


def _prune_unknown_after_refs(
    steps: list[str | dict[str, Any]],
    *,
    warnings: list[str],
) -> None:
    known_ids = {str(step["id"]) for step in steps if isinstance(step, dict) and step.get("id")}
    for step in steps:
        if not isinstance(step, dict) or not step.get("after"):
            continue
        dropped = _remove_unknown_after_refs(step, known_ids)
        if dropped:
            warnings.append(f"{step.get('id', step['uri'])}: removed unknown after {dropped!r}")


def ensure_step_ids(
    steps: list[str | dict[str, Any]], *, warnings: list[str]
) -> list[str | dict[str, Any]]:
    if not needs_explicit_ids(steps):
        return steps
    normalized = _assign_missing_step_ids(steps, warnings=warnings)
    _prune_unknown_after_refs(normalized, warnings=warnings)
    return normalized

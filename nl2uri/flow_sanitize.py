from __future__ import annotations

from typing import Any

from nl2uri.flow_helpers import build_sanitized_step, normalize_step_raw, supported_scheme


def _warn_invalid_step(warnings: list[str], index: int, detail: str) -> None:
    warnings.append(f"dropped step {index + 1}: {detail}")


def _sanitize_uri_step(uri: str, *, warnings: list[str], index: int) -> str | None:
    if not supported_scheme(uri):
        _warn_invalid_step(warnings, index, f"unsupported URI {uri!r}")
        return None
    return uri


def _normalized_step_uri(
    normalized: dict[str, Any],
    *,
    warnings: list[str],
    index: int,
) -> str | None:
    uri = str(normalized.get("uri") or "").strip()
    if not uri or "://" not in uri:
        _warn_invalid_step(warnings, index, "missing uri")
        return None
    if not supported_scheme(uri):
        _warn_invalid_step(warnings, index, f"unsupported scheme in {uri!r}")
        return None
    return uri


def sanitize_flow_step(raw: Any, *, warnings: list[str], index: int) -> str | dict[str, Any] | None:
    normalized = normalize_step_raw(raw)
    if normalized is None:
        _warn_invalid_step(warnings, index, f"invalid shape {raw!r}")
        return None
    if isinstance(normalized, str):
        return _sanitize_uri_step(normalized, warnings=warnings, index=index)

    uri = _normalized_step_uri(normalized, warnings=warnings, index=index)
    if uri is None:
        return None
    return build_sanitized_step({**normalized, "uri": uri})

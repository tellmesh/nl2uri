from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from nl2uri.planner_templates import generic_plan

Matcher = Callable[[str], bool]
Planner = Callable[[str], dict[str, Any]]


def _candidate_roots() -> list[Path]:
    candidates: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved not in candidates:
            candidates.append(resolved)

    cwd = Path.cwd()
    module_root = Path(__file__).resolve().parents[1]

    add(cwd)
    if raw := os.getenv("HYPERVISOR_REPO_ROOT"):
        add(Path(raw))
    for base in (cwd, module_root, *module_root.parents):
        add(base / "hypervisor")
        add(base / "wronai" / "hypervisor")
    try:
        from uri3.config.repo_root import find_repo_root

        add(find_repo_root(strict=False))
    except Exception:
        pass
    add(module_root)
    return candidates


def repo_root() -> Path:
    domain_roots = [candidate for candidate in _candidate_roots() if (candidate / "domains").is_dir()]
    for candidate in domain_roots:
        if (candidate / "contracts" / "registry.yaml").is_file():
            return candidate
    if domain_roots:
        return domain_roots[0]
    return Path(__file__).resolve().parents[1]


def _registry_roots() -> list[Path]:
    roots: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in roots and (resolved / "domains").is_dir():
            roots.append(resolved)

    for candidate in _candidate_roots():
        add(candidate)
    return roots


@dataclass(frozen=True)
class DomainRegistryEntry:
    domain_dir: str
    domain_id: str
    match_prompt: Matcher
    deterministic_plan: Planner
    fragment: dict[str, Any] = field(default_factory=dict)

    @property
    def flow_aliases(self) -> dict[str, str]:
        block = self.fragment.get("flow_aliases") or {}
        return block if isinstance(block, dict) else {}

    @property
    def default_deployment_id(self) -> str | None:
        value = self.fragment.get("default_deployment_id")
        return str(value) if value else None

    @property
    def default_health_uri(self) -> str | None:
        value = self.fragment.get("default_health_uri")
        return str(value) if value else None

    @property
    def default_card_uri(self) -> str | None:
        value = self.fragment.get("default_card_uri")
        return str(value) if value else None

    @property
    def deployment_selector_aliases(self) -> dict[str, str]:
        block = self.fragment.get("deployment_selector_aliases") or {}
        if not isinstance(block, dict):
            return {}
        return {str(key): str(value) for key, value in block.items()}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _find_callable(module: Any, *, prefix: str, suffix: str) -> Callable[..., Any] | None:
    for name in dir(module):
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    return None


def _load_planner_module(planner_path: Path) -> Any:
    module_name = f"domains.{planner_path.parent.name}.planner"
    spec = importlib.util.spec_from_file_location(module_name, str(planner_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load planner module from {planner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_domain_registry() -> tuple[DomainRegistryEntry, ...]:
    entries: list[DomainRegistryEntry] = []
    seen: set[str] = set()
    for root in _registry_roots():
        for planner_path in sorted((root / "domains").glob("*/planner.py")):
            if planner_path.parent.name in seen:
                continue
            module = _load_planner_module(planner_path)
            matcher = getattr(module, "match_prompt", None) or _find_callable(
                module,
                prefix="is_",
                suffix="_prompt",
            )
            planner_fn = getattr(module, "deterministic_plan", None) or _find_callable(
                module,
                prefix="deterministic_",
                suffix="_plan",
            )
            if matcher is None or planner_fn is None:
                continue
            fragment = _read_yaml(planner_path.parent / "registry.fragment.yaml")
            domain_id = str(fragment.get("domain_id") or planner_path.parent.name)
            entries.append(
                DomainRegistryEntry(
                    domain_dir=planner_path.parent.name,
                    domain_id=domain_id,
                    match_prompt=matcher,
                    deterministic_plan=planner_fn,
                    fragment=fragment,
                )
            )
            seen.add(planner_path.parent.name)
    return tuple(entries)


def match_domain(prompt: str) -> DomainRegistryEntry | None:
    for entry in load_domain_registry():
        if entry.match_prompt(prompt):
            return entry
    return None


def resolve_plan(prompt: str) -> dict[str, Any]:
    entry = match_domain(prompt)
    if entry is not None:
        return entry.deterministic_plan(prompt)
    return generic_plan(prompt)


def _weather_entry() -> DomainRegistryEntry | None:
    for entry in load_domain_registry():
        if entry.domain_dir == "weather_map":
            return entry
    return None


def is_weather_prompt(prompt: str) -> bool:
    entry = _weather_entry()
    return bool(entry and entry.match_prompt(prompt))


def deterministic_weather_plan(prompt: str) -> dict[str, Any]:
    entry = _weather_entry()
    if entry is not None:
        return entry.deterministic_plan(prompt)
    return generic_plan(prompt)

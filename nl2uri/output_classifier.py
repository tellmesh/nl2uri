from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

OUTPUT_KINDS = (
    "single_uri",
    "uri_list",
    "resource_tree",
    "uri_flow",
    "task_graph",
    "workflow_graph",
)

DOMAIN_WORDS = re.compile(
    r"\b(wygeneruj|generuj|stw[oó]rz|zbuduj|utw[oó]rz|dodaj|domain|domen[aę]|agenta|system)\b",
    re.I,
)
ACTION_WORDS = re.compile(
    r"\b(otw[oó]rz|sprawd[zź]|uruchom|kliknij|pobierz|zr[oó]b|screenshot|przejd[zź]|"
    r"je[sś]li|potem|nast[eę]pnie|po czym|verify|open|check|run|click|screenshot|restart)\b",
    re.I,
)
BROWSER_WORDS = re.compile(r"\b(chrome|przegl[aą]dark|browser|dom://|localhost)\b", re.I)
SEQUENTIAL_WORKFLOW = re.compile(
    r"\b(wygeneruj|generuj|stw[oó]rz).*(uruchom|run).*(sprawd[zź]|health|browser|chrome)\b",
    re.I | re.S,
)
CONDITION_WORDS = re.compile(r"\b(je[sś]li|if|gdy|restart|zrestartuj|nie dzia[lł]a)\b", re.I)
PARALLEL_WORDS = re.compile(r"\b(r[oó]wnoleg|parallel|jednocze[sś]nie|oraz.*oraz)\b", re.I)
READ_TARGETS = re.compile(r"\b(health|card|status|log|agent card)\b", re.I)
SINGLE_URI_WORDS = re.compile(r"\b(poka[zż]|status|health|card|agent)\b", re.I)


@dataclass(frozen=True)
class _PromptFlags:
    has_domain: bool
    has_actions: bool
    has_browser: bool
    has_condition: bool
    has_parallel: bool
    read_targets: int
    sequential: bool


def _prompt_flags(text: str) -> _PromptFlags:
    return _PromptFlags(
        has_domain=bool(DOMAIN_WORDS.search(text)),
        has_actions=bool(ACTION_WORDS.search(text)),
        has_browser=bool(BROWSER_WORDS.search(text)),
        has_condition=bool(CONDITION_WORDS.search(text)),
        has_parallel=bool(PARALLEL_WORDS.search(text)),
        read_targets=len(READ_TARGETS.findall(text)),
        sequential=bool(SEQUENTIAL_WORKFLOW.search(text)),
    )


def _rule_parallel_workflow(flags: _PromptFlags, _text: str) -> str | None:
    if flags.has_parallel and flags.has_actions:
        return "workflow_graph"
    return None


def _rule_conditional_workflow(flags: _PromptFlags, _text: str) -> str | None:
    if flags.has_condition and flags.has_actions and not flags.sequential:
        return "workflow_graph"
    return None


def _rule_sequential_flow(flags: _PromptFlags, _text: str) -> str | None:
    if flags.sequential:
        return "uri_flow"
    return None


def _rule_domain_only_tree(flags: _PromptFlags, _text: str) -> str | None:
    if flags.has_domain and not flags.has_actions:
        return "resource_tree"
    return None


def _rule_domain_with_actions(flags: _PromptFlags, _text: str) -> str | None:
    if flags.has_domain and flags.has_actions:
        return "uri_flow"
    return None


def _rule_multi_read_list(flags: _PromptFlags, _text: str) -> str | None:
    if flags.read_targets >= 2 and not flags.has_browser and not flags.has_condition:
        return "uri_list"
    return None


def _rule_browser_flow(flags: _PromptFlags, _text: str) -> str | None:
    if flags.has_browser and flags.has_actions:
        return "uri_flow"
    return None


def _rule_action_only(flags: _PromptFlags, _text: str) -> str | None:
    if not (flags.has_actions and not flags.has_domain):
        return None
    return "uri_flow" if not flags.has_condition else "workflow_graph"


def _rule_read_list(flags: _PromptFlags, _text: str) -> str | None:
    if flags.read_targets >= 2:
        return "uri_list"
    return None


def _rule_single_uri_words(_flags: _PromptFlags, text: str) -> str | None:
    if SINGLE_URI_WORDS.search(text):
        return "single_uri"
    return None


def _rule_domain_fallback(flags: _PromptFlags, _text: str) -> str | None:
    if flags.has_domain:
        return "resource_tree"
    return None


_CLASSIFICATION_RULES: tuple[Callable[[_PromptFlags, str], str | None], ...] = (
    _rule_parallel_workflow,
    _rule_conditional_workflow,
    _rule_sequential_flow,
    _rule_domain_only_tree,
    _rule_domain_with_actions,
    _rule_multi_read_list,
    _rule_browser_flow,
    _rule_action_only,
    _rule_read_list,
    _rule_single_uri_words,
    _rule_domain_fallback,
)


def classify_output_kind(prompt: str) -> str:
    text = prompt.strip()
    if not text:
        return "single_uri"

    flags = _prompt_flags(text)
    for rule in _CLASSIFICATION_RULES:
        if kind := rule(flags, text):
            return kind
    return "single_uri"

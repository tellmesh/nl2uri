from __future__ import annotations

import json
import os
from typing import Any

import typer
import yaml

from nl2uri.flow_planner import plan_flow
from nl2uri.flow_repair import repair_and_validate_flow, repair_flow_body, validate_expanded_flow
from nl2uri.graph_planner import plan_auto, plan_by_kind, plan_list, plan_single, plan_task, plan_tree, plan_workflow_graph
from nl2uri.output_classifier import classify_output_kind
from nl2uri.domain_planner import plan_from_prompt
from nl2uri.writer import write_uri_tree
from uri3.graph import dry_run_workflow, validate_workflow_graph
from uri3.validators.uri_tree_validator import validate_uri_tree

app = typer.Typer(help="nl2uri: natural language -> URI plans (single, list, tree, flow, task, graph)")


def _default_use_llm() -> bool:
    return os.getenv("NL2URI_USE_LLM", os.getenv("NL2A_USE_LLM", "0")) in {"1", "true", "TRUE", "yes"}


def _resolve_use_llm(*, llm: bool, no_llm: bool) -> bool:
    if llm and no_llm:
        raise typer.BadParameter("Use either --llm or --no-llm, not both")
    if llm:
        return True
    if no_llm:
        return False
    return _default_use_llm()


def _emit(payload: dict[str, Any], *, json_out: bool) -> None:
    typer.echo(
        json.dumps(payload, indent=2, ensure_ascii=False)
        if json_out
        else yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    )


def _validate_flow_payload(payload: dict[str, Any]) -> list[str]:
    try:
        return validate_expanded_flow(payload)
    except ValueError as exc:
        typer.echo("Flow validation failed:", err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _plan_command(
    prompt: str,
    *,
    kind: str,
    json_out: bool,
    use_llm: bool,
    validate: bool,
) -> None:
    payload = plan_by_kind(prompt, kind=kind, use_llm=use_llm)
    if validate and kind in {"uri_flow", "task_graph", "workflow_graph"}:
        if kind == "uri_flow":
            _validate_flow_payload(payload)
        else:
            errors = validate_workflow_graph(payload)
            if errors:
                typer.echo("Workflow graph validation failed:", err=True)
                for error in errors:
                    typer.echo(error, err=True)
                raise typer.Exit(1)
    _emit(payload, json_out=json_out)


@app.command()
def plan(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
    llm: bool = typer.Option(False, "--llm", help="Use LLM graph planner when kind is task/workflow"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    validate: bool = typer.Option(False, "--validate", help="Validate task/workflow output with uri3"),
):
    """Classify prompt and generate the best matching URI plan."""
    payload = plan_auto(prompt, use_llm=_resolve_use_llm(llm=llm, no_llm=no_llm))
    if validate and payload["nl2uri"]["kind"] in {"uri_flow", "task_graph", "workflow_graph"}:
        if payload["nl2uri"]["kind"] == "uri_flow":
            _validate_flow_payload(payload)
        else:
            errors = validate_workflow_graph(payload)
            if errors:
                typer.echo("Workflow graph validation failed:", err=True)
                for error in errors:
                    typer.echo(error, err=True)
                raise typer.Exit(1)
    _emit(payload, json_out=json_out)


@app.command()
def classify(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
):
    payload = {"prompt": prompt, "kind": classify_output_kind(prompt)}
    _emit(payload, json_out=json_out)


@app.command()
def single(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
    no_llm: bool = typer.Option(False, "--no-llm"),
):
    _plan_command(prompt, kind="single_uri", json_out=json_out, use_llm=not no_llm, validate=False)


@app.command("list")
def list_cmd(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
    no_llm: bool = typer.Option(False, "--no-llm"),
):
    _plan_command(prompt, kind="uri_list", json_out=json_out, use_llm=not no_llm, validate=False)


@app.command()
def tree(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    out: str = typer.Option("", "--out"),
    json_out: bool = typer.Option(False, "--json"),
    no_llm: bool = typer.Option(False, "--no-llm"),
):
    payload = plan_tree(prompt, use_llm=not no_llm)
    if out:
        path = write_uri_tree(payload["uri_tree"], out)
        errors = validate_uri_tree(path)
        if errors:
            typer.echo("URI Tree validation failed:", err=True)
            for error in errors:
                typer.echo(error, err=True)
            raise typer.Exit(1)
        typer.echo(str(path))
        return
    _emit(payload, json_out=json_out)


@app.command()
def flow(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
    llm: bool = typer.Option(False, "--llm", help="Use LLM compact flow planner with repair/validate"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    validate: bool = typer.Option(False, "--validate", help="Validate compact flow, expand, and validate workflow graph"),
    repair: bool = typer.Option(False, "--repair", help="Repair/normalize compact flow before output"),
    expand: bool = typer.Option(False, "--expand", help="Print expanded workflow_graph after compact flow"),
):
    """Generate compact URI flow (*.uri.flow.yaml style)."""
    payload = plan_flow(prompt, use_llm=_resolve_use_llm(llm=llm, no_llm=no_llm))
    if repair:
        body, repair_warnings = repair_flow_body(payload, prompt)
        payload = {**payload, **body}
        if repair_warnings:
            payload["repair_warning"] = "; ".join(repair_warnings)
    if validate:
        flow_warnings = _validate_flow_payload(payload)
        for warning in flow_warnings:
            typer.echo(f"warning: {warning}", err=True)
    if expand:
        from uri2flow import expand_flow

        _emit(expand_flow(payload), json_out=json_out)
        return
    _emit(payload, json_out=json_out)


@app.command()
def task(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
    llm: bool = typer.Option(False, "--llm", help="Use LLM graph planner with registry injection"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    validate: bool = typer.Option(False, "--validate"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build uri3 execution plan"),
):
    payload = plan_task(prompt, use_llm=_resolve_use_llm(llm=llm, no_llm=no_llm))
    if validate:
        errors = validate_workflow_graph(payload)
        if errors:
            typer.echo("Task graph validation failed:", err=True)
            for error in errors:
                typer.echo(error, err=True)
            raise typer.Exit(1)
    if dry_run:
        payload = dry_run_workflow(payload)
    _emit(payload, json_out=json_out)


@app.command()
def graph(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    json_out: bool = typer.Option(False, "--json"),
    llm: bool = typer.Option(False, "--llm", help="Use LLM graph planner with registry injection"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    validate: bool = typer.Option(False, "--validate"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build uri3 execution plan"),
):
    payload = plan_workflow_graph(prompt, use_llm=_resolve_use_llm(llm=llm, no_llm=no_llm))
    if validate:
        errors = validate_workflow_graph(payload)
        if errors:
            typer.echo("Workflow graph validation failed:", err=True)
            for error in errors:
                typer.echo(error, err=True)
            raise typer.Exit(1)
    if dry_run:
        payload = dry_run_workflow(payload)
    _emit(payload, json_out=json_out)


@app.command()
def generate(
    prompt: str = typer.Option(..., "-p", "--prompt"),
    out: str = typer.Option("", "--out"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    json_out: bool = typer.Option(False, "--json"),
):
    """Backward-compatible URI Tree generation."""
    tree = plan_from_prompt(prompt, use_llm=not no_llm)
    if out:
        path = write_uri_tree(tree, out)
        errors = validate_uri_tree(path)
        if errors:
            typer.echo("URI Tree validation failed:", err=True)
            for error in errors:
                typer.echo(error, err=True)
            raise typer.Exit(1)
        typer.echo(str(path))
        return
    _emit({"uri_tree": tree}, json_out=json_out)


def main():
    app()


if __name__ == "__main__":
    main()

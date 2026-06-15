from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path

from nl2uri.domain_planner import plan_from_prompt
from nl2uri.writer import write_uri_tree
from uri3.validators.uri_tree_validator import validate_uri_tree

WEATHER_PROMPT = "generuj mape pogody dwa tygodnie do przodu w html"


@dataclass
class PipelineResult:
    domain_dir: Path
    tree_path: Path
    files: dict[str, str]
    deployment_id: str | None = None


@dataclass
class FullPipelineResult(PipelineResult):
    agent_spec_path: Path | None = None
    generated_agent_dir: Path | None = None
    registry_resolved_path: Path | None = None
    verify_errors: list[str] = field(default_factory=list)


def generate_tree(prompt: str, *, no_llm: bool = False) -> dict:
    return plan_from_prompt(prompt, use_llm=not no_llm)


def _append_pipeline_logs(*, tree: dict, deployment_id: str | None, root: Path) -> None:
    try:
        from uri3.logs.writer import append_log

        append_log(
            "nl2a",
            "Domain pack generated",
            logger="nl2uri.pipeline",
            domain_id=tree.get("domain", {}).get("id"),
            deployment_id=deployment_id,
            root=root,
        )
        append_log(
            "hypervisor",
            "Deployment registry synced",
            logger="hypervisor.deployment_registry",
            deployment_id=deployment_id,
            root=root,
        )
    except FileNotFoundError:
        pass


def run_generate_pipeline(
    prompt: str,
    *,
    no_llm: bool = False,
    out_dir: str = "domains",
    root: str | Path = ".",
) -> PipelineResult:
    from hypervisor.deployment_registry.status import sync_from_uri_tree
    from hypervisor.domain_pack.generator import generate_domain_pack

    tree = generate_tree(prompt, no_llm=no_llm)
    domain_dir = Path(out_dir) / tree["domain"]["id"]
    tree_path = write_uri_tree(tree, domain_dir / "uri_tree.yaml")

    errors = validate_uri_tree(tree_path)
    if errors:
        raise ValueError("URI Tree validation failed: " + "; ".join(errors))

    files = generate_domain_pack(tree_path, domain_dir, root=Path(root))
    deployment = sync_from_uri_tree(tree, root=root)
    _append_pipeline_logs(tree=tree, deployment_id=deployment.id if deployment else None, root=Path(root))
    return PipelineResult(
        domain_dir=domain_dir,
        tree_path=Path(tree_path),
        files=files,
        deployment_id=deployment.id if deployment else None,
    )


def run_full_pipeline(
    prompt: str,
    *,
    no_llm: bool = False,
    out_dir: str = "domains",
    root: str | Path = ".",
) -> FullPipelineResult:
    from generator.agent_generator import generate_agent
    from generator.verify import verify_generated_agent
    from hypervisor.contract_registry.registry_builder import write_registry_manifest

    root = Path(root)
    base = run_generate_pipeline(prompt, no_llm=no_llm, out_dir=out_dir, root=root)

    agent_spec_path = Path(base.files["agent_contract"])
    generated_root = root / "agents" / "generated"
    generated_agent_dir = generate_agent(agent_spec_path, output_root=generated_root)

    registry_resolved_path = write_registry_manifest(
        root,
        root / "output" / "contract_registry.resolved.json",
    )

    verify_errors = verify_generated_agent(generated_agent_dir)
    if verify_errors:
        raise ValueError("Agent verification failed: " + "; ".join(verify_errors))

    # Read the marker to get the canonical file:// for the markpact README of the generated agent
    marker_path = generated_agent_dir / ".generated.yaml"
    markpact_readme_uri = None
    try:
        marker = yaml.safe_load(marker_path.read_text(encoding="utf-8")) or {}
        markpact_readme_uri = marker.get("markpact_readme")
    except Exception:
        pass

    try:
        from uri3.logs.writer import append_log

        append_log(
            "nl2a",
            "Full pipeline completed",
            logger="nl2uri.pipeline",
            agent_dir=str(generated_agent_dir),
            markpact_readme=markpact_readme_uri or str(generated_agent_dir / "README.md"),
            root=Path(root),
        )
        append_log(
            "factory",
            "Agent generated and verified",
            logger="generator.verify",
            agent_dir=str(generated_agent_dir),
            markpact_readme=markpact_readme_uri,
            root=Path(root),
        )
    except FileNotFoundError:
        pass

    return FullPipelineResult(
        domain_dir=base.domain_dir,
        tree_path=base.tree_path,
        files=base.files,
        deployment_id=base.deployment_id,
        agent_spec_path=agent_spec_path,
        generated_agent_dir=generated_agent_dir,
        registry_resolved_path=registry_resolved_path,
        verify_errors=verify_errors,
    )

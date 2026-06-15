"""End-to-end nl2a pipeline tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from generator.validate import validate_agent
from generator.verify import verify_generated_agent
from hypervisor.deployment_registry import get_deployment_for_agent, load_deployment_registry
from nl2a.cli import app
from nl2uri.pipeline import WEATHER_PROMPT, run_full_pipeline


@pytest.fixture
def isolated_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for relative in (
        "contracts/agents",
        "contracts/proto",
        "contracts/compatibility",
        "deployments",
        "domains",
        "output",
        "agents/generated",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    shutil.copytree(repo_root / "schemas", tmp_path / "schemas")
    shutil.copy(repo_root / "contracts" / "registry.yaml", tmp_path / "contracts" / "registry.yaml")
    policy_src = repo_root / "contracts" / "compatibility" / "policy.yaml"
    if policy_src.exists():
        shutil.copy(policy_src, tmp_path / "contracts" / "compatibility" / "policy.yaml")

    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_nl2a_full_pipeline_weather_map(isolated_project: Path):
    result = run_full_pipeline(WEATHER_PROMPT, no_llm=True, out_dir="domains", root=isolated_project)

    assert result.tree_path.exists()
    assert (result.domain_dir / "uri_tree.yaml").exists()
    assert (result.domain_dir / "resources.yaml").exists()
    assert (result.domain_dir / "views.yaml").exists()
    assert (result.domain_dir / "commands.yaml").exists()
    assert (result.domain_dir / "registry.fragment.yaml").exists()

    assert result.agent_spec_path is not None
    assert result.agent_spec_path.exists()
    assert validate_agent(result.agent_spec_path) == []

    assert result.generated_agent_dir is not None
    assert (result.generated_agent_dir / "main.py").exists()
    assert (result.generated_agent_dir / "routes.py").exists()
    assert verify_generated_agent(result.generated_agent_dir) == []

    assert result.registry_resolved_path is not None
    assert result.registry_resolved_path.exists()
    manifest = json.loads(result.registry_resolved_path.read_text(encoding="utf-8"))
    assert manifest["contract_hash"].startswith("sha256:")
    assert manifest["counts"]["capabilities"] >= 2

    registry = load_deployment_registry(isolated_project)
    deployment = get_deployment_for_agent("agent://weather-map-agent", registry=registry)
    assert deployment is not None
    assert deployment.target_uri == "local://agents/generated/weather_map_agent"


def test_nl2a_cli_generate_no_llm(isolated_project: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["-p", WEATHER_PROMPT, "--no-llm", "--out-dir", "domains"],
    )
    assert result.exit_code == 0, result.output

    domain_dir = isolated_project / "domains" / "weather_map"
    assert domain_dir.exists()
    assert (domain_dir / "uri_tree.yaml").exists()
    assert (isolated_project / "contracts" / "agents" / "weather_map_agent.yaml").exists()
    assert (isolated_project / "agents" / "generated" / "weather_map_agent" / "main.py").exists()
    assert (isolated_project / "output" / "contract_registry.resolved.json").exists()

    verify_errors = verify_generated_agent(
        isolated_project / "agents" / "generated" / "weather_map_agent"
    )
    assert verify_errors == []

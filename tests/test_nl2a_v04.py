from pathlib import Path

from hypervisor.domain_pack.generator import generate_domain_pack_from_tree
from nl2uri.domain_planner import plan_from_prompt


def test_weather_prompt_generates_uri_tree():
    tree = plan_from_prompt("generuj mape pogody dwa tygodnie do przodu w html", use_llm=False)
    assert tree["domain"]["id"] == "weather_map"
    assert tree["inputs"]["days"]["default"] == 14
    assert "html_map" in tree["resources"]
    assert tree["resources"]["html_map"]["renderer_ref"] == "html"


def test_domain_pack_generation(tmp_path):
    tree = plan_from_prompt("generuj mape pogody dwa tygodnie do przodu w html", use_llm=False)
    files = generate_domain_pack_from_tree(tree, tmp_path / "weather_map")
    assert Path(files["uri_tree"]).exists()
    assert Path(files["resources"]).exists()
    assert Path(files["agent_contract"]).exists()
    assert Path(files["views"]).exists()
    assert Path(files["commands"]).exists()

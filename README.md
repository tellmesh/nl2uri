# nl2uri


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.5.8-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$0.37-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-2.5h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $0.3690 (4 commits)
- 👤 **Human dev:** ~$255 (2.5h @ $100/h, 30min dedup)

Generated on 2026-06-15 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

TellMesh URI package extracted from [tellmesh/tellmesh](https://github.com/tellmesh/tellmesh).

**Role:** natural language → URI plans (single, list, tree, compact flow, task graph, workflow graph).

```text
prompt -> nl2uri plan/graph/flow/task -> uri3 validate/run -> uri2ops import-graph (operator slice)
```

## Install

```bash
pip install -e .
# LLM planners need OpenRouter key:
set -a && source .env && set +a   # OPENROUTER_API_KEY
```

## CLI quickstart

```bash
nl2uri plan -p "open browser and check health" --validate
nl2uri flow -p "weather agent health check" --expand --validate
nl2uri graph -p "browser health check with dom assert" --llm --validate --dry-run
nl2uri task -p "android screenshot" --llm --validate
nl2uri tree -p "weather map agent" --out output/weather.uri.tree.yaml
nl2uri generate -p "invoices agent with health" --out output/invoices.uri.tree.yaml

# Operator bridge (graph YAML -> uri2ops task):
nl2uri graph -p "..." --llm -o /tmp/graph.yaml
uri2ops import-graph /tmp/graph.yaml --validate --out /tmp/task.yaml
uri2ops run /tmp/task.yaml --adapter mock --approve
```

## Examples

| Example | Path |
|---------|------|
| NL → graph (LLM) | [`tellmesh/examples/16_llm_graph_planner`](../tellmesh/examples/16_llm_graph_planner) |
| NL → flow | [`tellmesh/examples/18_llm_flow_planner`](../tellmesh/examples/18_llm_flow_planner) |
| Multi-URI graph | [`tellmesh/examples/13_nl2uri_multi_uri_graph`](../tellmesh/examples/13_nl2uri_multi_uri_graph) |
| Operator bridge | [`uri2ops/examples/16_nl2uri_operator_bridge`](../uri2ops/examples/16_nl2uri_operator_bridge) |

## Links

- [TODO](TODO.md) · [CHANGELOG](CHANGELOG.md)
- [uri3](../uri3) · [uri2flow](../uri2flow) · [uri2ops](../uri2ops)
- Org status: [`../TODO_STATUS.md`](../TODO_STATUS.md)


## License

Licensed under Apache-2.0.

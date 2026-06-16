# TODO — nl2uri

**Version:** 0.5.8 · **Role:** natural language → URI tree / task / workflow / flow

> Utworzono: 2026-06-16

## Zrobione

- [x] Output kinds: single, list, tree, task_graph, workflow_graph, uri_flow
- [x] Rule-based + LLM graph/flow planners (OpenRouter via uri3 profiles)
- [x] Graph repair + operation registry injection
- [x] CLI: `plan`, `graph`, `task`, `flow`, `tree`, `generate`
- [x] `flow --expand` → uri2flow

## Otwarte

- [ ] CLI `graph --to-uri2ops` (dziś: osobno `uri2ops import-graph`)
- [ ] Lepszy komunikat gdy OPENROUTER 401 (preflight key check)
- [ ] Testy E2E nl2uri → uri2ops bez tellmesh monorepo path

## Cross-package

| Krok | Narzędzie |
|------|-----------|
| Plan NL | nl2uri |
| Operator slice | uri2ops import-graph |
| Full workflow | uri3 run-workflow |

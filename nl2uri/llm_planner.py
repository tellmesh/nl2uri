from nl2uri.domain_planner import plan_from_prompt
from nl2uri.planner import PlanResult


def llm_plan(prompt: str) -> PlanResult:
    tree = plan_from_prompt(prompt, use_llm=True)
    used_llm = "planner_warning" not in tree or "deterministic" not in str(tree.get("planner_warning", ""))
    return PlanResult(tree, used_llm=used_llm)

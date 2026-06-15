from dataclasses import dataclass

from nl2uri.domain_planner import plan_from_prompt


@dataclass
class PlanResult:
    tree: dict
    used_llm: bool = False


def rule_based_plan(prompt: str) -> PlanResult:
    return PlanResult(plan_from_prompt(prompt, use_llm=False), used_llm=False)

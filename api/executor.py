"""
Executor — runs the skill's system prompt against the chosen model.
Optionally runs a reviewer pass for high-risk/high-complexity requests.
Falls back gracefully if a provider is down.
"""

import logging
import time
from adapters import get_adapter, AdapterResponse
from skills.registry import REGISTRY
from skills.pricing import estimate_cost
from .models import ClassifierOutput

log = logging.getLogger("askai.executor")

FALLBACK_MODEL = "claude-sonnet-4-6"


async def _call(model_key: str, system: str, user: str, max_tokens: int = 4096) -> AdapterResponse:
    """Try the requested model, fall back if it fails."""
    try:
        adapter = get_adapter(model_key)
        start = time.time()
        result = await adapter.complete(system=system, user=user, max_tokens=max_tokens)
        elapsed = time.time() - start
        log.info("  MODEL %s responded in %.1fs (%d in / %d out tokens)",
                 model_key, elapsed, result.input_tokens, result.output_tokens)
        return result
    except Exception as e:
        log.warning("  MODEL %s FAILED: %s — falling back to %s", model_key, e, FALLBACK_MODEL)
        adapter = get_adapter(FALLBACK_MODEL)
        start = time.time()
        result = await adapter.complete(system=system, user=user, max_tokens=max_tokens)
        elapsed = time.time() - start
        log.info("  FALLBACK %s responded in %.1fs (%d in / %d out tokens)",
                 FALLBACK_MODEL, elapsed, result.input_tokens, result.output_tokens)
        return result


def _should_review(classifier: ClassifierOutput) -> bool:
    """Decide if this request warrants a second opinion."""
    needs_review = (
        classifier.risk == "high"
        or classifier.complexity == "high"
        or (classifier.risk == "medium" and classifier.depth == "deep")
    )
    if needs_review:
        log.info("  REVIEW TRIGGERED: risk=%s complexity=%s depth=%s",
                 classifier.risk, classifier.complexity, classifier.depth)
    return needs_review


async def execute(
    prompt: str,
    classifier: ClassifierOutput,
) -> dict:
    """
    Run the primary skill agent, optionally run a reviewer.
    Returns dict with: answer, model_used, reviewed, cost_usd
    """
    skill = REGISTRY[classifier.skill]
    system = skill["system_prompt"] + f"\n\nOutput rules: {skill['output_rules']}"

    log.info("EXECUTING: skill=%s (%s) on model=%s",
             classifier.skill, skill["name"], classifier.model)

    # Inject classifier context so the skill knows what it's dealing with
    enriched = (
        f"[Context: industry={classifier.industry}, "
        f"task={classifier.task_type}, "
        f"complexity={classifier.complexity}, "
        f"depth={classifier.depth}]\n\n"
        f"{prompt}"
    )

    # Primary call
    result = await _call(classifier.model, system, enriched)
    total_cost = estimate_cost(classifier.model, result.input_tokens, result.output_tokens)
    answer = result.text
    model_used = result.model
    reviewed = False

    log.info("  PRIMARY COST: $%.6f", total_cost)

    # Reviewer pass
    if _should_review(classifier) and skill.get("reviewer"):
        reviewer_key = skill["reviewer"]
        reviewer_skill = REGISTRY[reviewer_key]
        reviewer_system = reviewer_skill["system_prompt"]

        log.info("  REVIEWING with skill=%s (%s)", reviewer_key, reviewer_skill["name"])

        review_prompt = (
            "A colleague responded to this request. "
            "Correct errors, strengthen weak points, return the best possible final answer.\n\n"
            f"ORIGINAL REQUEST:\n{prompt}\n\n"
            f"COLLEAGUE'S RESPONSE:\n{answer}"
        )

        # Reviewer always uses a premium model — this is the "second opinion"
        reviewer_model = "claude-opus-4-6"
        review_result = await _call(reviewer_model, reviewer_system, review_prompt)
        review_cost = estimate_cost(reviewer_model, review_result.input_tokens, review_result.output_tokens)
        total_cost += review_cost

        log.info("  REVIEW COST: $%.6f", review_cost)

        answer = review_result.text
        model_used = f"{result.model} -> {review_result.model}"
        reviewed = True
    elif not skill.get("reviewer"):
        log.info("  NO REVIEWER defined for this skill — skipping review")
    else:
        log.info("  REVIEW NOT NEEDED for this risk/complexity level")

    log.info("TOTAL COST: $%.6f | reviewed=%s", total_cost, reviewed)
    log.info("ANSWER PREVIEW: %s", answer[:200].replace("\n", " ") + ("..." if len(answer) > 200 else ""))
    log.info("=" * 60)

    return {
        "answer": answer,
        "model_used": model_used,
        "reviewed": reviewed,
        "cost_usd": round(total_cost, 6),
    }

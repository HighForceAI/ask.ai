"""
The classifier is the brain of ask.ai.

One LLM call. It reads the user's prompt and decides:
  1. Which skill (expert persona) handles this
  2. Which model (from any provider) is best for this specific request
  3. Metadata: industry, task type, complexity, risk, depth

No routing table. No hardcoded rules. The LLM reasons about the best
match every time, using the full skill menu and model catalog.
"""

import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

import anthropic
from .models import ClassifierOutput
from skills.registry import SKILL_MENU, SKILL_KEYS
from adapters import VALID_MODELS

log = logging.getLogger("askai.classifier")
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _build_classifier_prompt() -> str:
    model_menu = """Available models (pick the best one for THIS specific request):
  "claude-opus-4-6":   Anthropic premium — best for coding, nuanced reasoning, regulated industries
  "claude-sonnet-4-6": Anthropic mid — great general workhorse, instruction following, structured output
  "claude-haiku-4-5":  Anthropic fast — classification, support, simple high-volume tasks
  "gpt-5.2":           OpenAI mid — strong at creative writing, business writing, content
  "gpt-5.4-mini":      OpenAI fast — speed, simple tasks, high-volume
  "o3":                OpenAI reasoning — hard math, multi-step logic, science, complex risk analysis
  "gemini-3-pro":      Google premium — math, data analysis, very long documents, multimodal
  "gemini-2.5-flash":  Google fast — cheapest capable model, long-context budget tasks
  "grok-4.1":          xAI — real-time web search, social signals, market intelligence, trends
  "deepseek-v3.2":     DeepSeek — best value, general tasks, solid fallback
  "deepseek-r1":       DeepSeek reasoning — math, logic, budget alternative to o3"""

    json_schema = """{
  "skill": "<skill key from the list above>",
  "model": "<model key from the list above>",
  "industry": "<saas|legal|finance|healthcare|marketing|engineering|education|science|design|hr|operations|media|government|general>",
  "task_type": "<analysis|writing|coding|research|strategy|review|explain|calculate|create|advise|debug|plan|support>",
  "complexity": "<low|medium|high>",
  "risk": "<low|medium|high>",
  "depth": "<quick|standard|deep>",
  "reasoning": "<one sentence explaining your skill and model choice>"
}"""

    return f"""You are the routing brain of ask.ai. Given a user's prompt, you decide
which expert skill handles it and which AI model is best for this specific request.

## Available skills
{SKILL_MENU}

## {model_menu}

## Model selection guidelines
- Use premium models (opus, o3, gemini-3-pro) only when the task genuinely requires it:
  complex reasoning, high-stakes analysis, code review, legal/financial risk
- Use mid-tier (sonnet, gpt-5.2) for most substantive work
- Use fast/cheap (haiku, gpt-5.4-mini, gemini-2.5-flash, deepseek-v3.2) for simple tasks,
  support drafts, classification, quick questions
- Use grok-4.1 when the task benefits from real-time web data or social signals
- Use o3 or deepseek-r1 for tasks requiring extended reasoning chains (math, logic proofs)
- When in doubt, prefer mid-tier — best cost/quality tradeoff

## Risk assessment
- risk = high: output could cause financial, legal, or reputational harm if wrong
- risk = medium: output matters but errors are recoverable
- risk = low: casual, informational, low stakes

## Output format
Return ONLY valid JSON matching this exact schema — no markdown, no explanation:

{json_schema}

Respond with JSON only. No other text."""


CLASSIFIER_PROMPT = _build_classifier_prompt()


async def classify(prompt: str) -> ClassifierOutput:
    """Classify a user prompt into skill + model + metadata."""
    log.info("=" * 60)
    log.info("CLASSIFYING: %s", prompt[:120] + ("..." if len(prompt) > 120 else ""))

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # fast + cheap for routing
        max_tokens=300,
        system=CLASSIFIER_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    log.info("CLASSIFIER RAW: %s", raw)

    # Strip markdown fences if the model wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)

    # Safety: fall back if classifier picks invalid skill or model
    if data.get("skill") not in SKILL_KEYS:
        log.warning("CLASSIFIER picked unknown skill '%s' — falling back to generalist", data.get("skill"))
        data["skill"] = "generalist"
    if data.get("model") not in VALID_MODELS:
        log.warning("CLASSIFIER picked unknown model '%s' — falling back to sonnet", data.get("model"))
        data["model"] = "claude-sonnet-4-6"

    result = ClassifierOutput(**data)

    log.info("DECISION: skill=%s | model=%s | %s/%s | complexity=%s risk=%s depth=%s",
             result.skill, result.model, result.industry, result.task_type,
             result.complexity, result.risk, result.depth)
    log.info("REASONING: %s", result.reasoning)

    return result

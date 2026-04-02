# ask.ai

One prompt in, one expert answer out.

Most AI tools give you one model with one personality. ask.ai gives you **22 expert specialists across 11 models from 6 providers** — and automatically picks the right expert and the right model for every question. High-stakes legal question? Opus with a reviewer pass. Quick support reply? Haiku in 2 seconds. Market research? Grok with live web access. You don't choose. The system reasons about it for you.

The entire framework is ~1,300 lines of Python. No LangChain, no vector databases, no config files. Just a classifier, a skill registry, and provider adapters. It's our own framework: **classify → route → execute → review**.

---

## Table of contents

- [How it works](#how-it-works)
- [Architecture deep dive](#architecture-deep-dive)
- [The classifier — how it thinks](#the-classifier--how-it-thinks)
- [The skill registry — 22 experts](#the-skill-registry--22-experts)
- [The adapter layer — 6 providers, 11 models](#the-adapter-layer--6-providers-11-models)
- [The executor — execution + auto-review](#the-executor--execution--auto-review)
- [The API layer](#the-api-layer)
- [The SDK](#the-sdk)
- [Cost tracking](#cost-tracking)
- [Logging — full thought process](#logging--full-thought-process)
- [Project structure](#project-structure)
- [How to extend](#how-to-extend)
- [Quickstart](#quickstart)
- [API reference](#api-reference)
- [Design decisions](#design-decisions)
- [Why this exists](#why-this-exists)

---

## How it works

You send a prompt. The system does four things:

1. **Classify** — A fast, cheap LLM (Haiku) reads your prompt and decides: which expert skill should handle this, which model from which provider is best for this specific request, and metadata about the request (industry, task type, complexity, risk, depth). This takes ~2 seconds and costs fractions of a cent.

2. **Route** — The classifier's output directly determines which skill system prompt to use and which model adapter to call. There is no routing table or hardcoded rules. The classifier LLM reasons about the best match.

3. **Execute** — The chosen skill's system prompt is sent to the chosen model via the appropriate provider adapter. The skill prompt contains the expert persona, methodology, frameworks, and output formatting rules. The user's prompt is enriched with the classifier's metadata so the skill knows the context.

4. **Review (conditional)** — If the classifier flagged the request as high-risk, high-complexity, or medium-risk with deep depth, the system automatically runs a second pass. A different expert skill (the primary skill's designated reviewer) checks the answer on a premium model (Opus), corrects errors, strengthens weak points, and returns the final answer.

The response includes: the answer, which skill was used, which model(s), whether it was reviewed, the classifier's full reasoning, and the exact cost in USD.

```python
from sdk import AskAI

client = AskAI(api_key="dev-key-123", base_url="http://localhost:8000")
result = client.ask("Should we take the $4M SAFE at $20M cap or wait for revenue?")

print(result.answer)       # the expert answer
print(result.skill_used)   # "Startup Advisor"
print(result.model_used)   # "claude-opus-4-6 -> claude-opus-4-6"
print(result.reviewed)     # True — high-risk triggered auto-review
print(result.cost_usd)     # $0.0837
print(result.classifier.reasoning)  # "High-stakes fundraising decision..."
```

---

## Architecture deep dive

```
User prompt
    │
    ▼
┌──────────────────────────────────────────┐
│  CLASSIFIER  (api/classifier.py)         │
│  Model: claude-haiku-4-5 (fast, cheap)   │
│                                          │
│  Input: user's raw prompt                │
│  Output: JSON with 8 fields:             │
│    - skill    (which expert persona)     │
│    - model    (which LLM from which co)  │
│    - industry (domain of the request)    │
│    - task_type (what user wants done)    │
│    - complexity (low/medium/high)        │
│    - risk      (low/medium/high)         │
│    - depth     (quick/standard/deep)     │
│    - reasoning (why these choices)       │
│                                          │
│  The classifier sees the full skill menu │
│  (all 22 skill names + tags) and the     │
│  full model catalog (all 11 models +     │
│  what each is best at). It reasons about │
│  the best match for THIS specific prompt.│
│  No routing table. Pure LLM reasoning.   │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  EXECUTOR  (api/executor.py)             │
│                                          │
│  1. Looks up the skill from the registry │
│     (gets system prompt + output rules)  │
│  2. Gets the adapter for the chosen model│
│     (Anthropic/OpenAI/Google/xAI/DeepSk) │
│  3. Enriches the user prompt with the    │
│     classifier's metadata as context     │
│  4. Calls the model via the adapter      │
│  5. Calculates cost from token counts    │
│                                          │
│  If risk=high OR complexity=high OR      │
│  (risk=medium AND depth=deep):           │
│  ┌────────────────────────────────────┐  │
│  │  REVIEWER PASS                     │  │
│  │  Model: always claude-opus-4-6     │  │
│  │  Skill: the primary skill's        │  │
│  │         designated reviewer         │  │
│  │                                    │  │
│  │  Gets both the original prompt AND │  │
│  │  the primary answer. Instructed to │  │
│  │  correct errors, strengthen weak   │  │
│  │  points, return the best possible  │  │
│  │  final answer.                     │  │
│  └────────────────────────────────────┘  │
│                                          │
│  If the chosen model fails (provider     │
│  down, auth error, timeout), falls back  │
│  to claude-sonnet-4-6 automatically.     │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  RESPONSE  (api/models.py → AskResponse) │
│                                          │
│  {                                       │
│    answer: string,                       │
│    skill_used: "Startup Advisor",        │
│    model_used: "claude-opus-4-6",        │
│    reviewed: true,                       │
│    cost_usd: 0.0837,                     │
│    classifier: { full classification }   │
│  }                                       │
└──────────────────────────────────────────┘
```

---

## The classifier — how it thinks

**File:** `api/classifier.py`

The classifier is the brain. It's a single LLM call to Haiku (fast, cheap) with a carefully engineered system prompt that contains:

1. **The skill menu** — auto-generated from the registry at import time. Lists every skill key, name, and tags. Example: `"startup_advisor": Startup Advisor — strategy, fundraising, business model, pitch, startup`

2. **The model catalog** — hardcoded list of all 11 available models with what each is best at. Example: `"grok-4.1": xAI — real-time web search, social signals, market intelligence, trends`

3. **Model selection guidelines** — rules for when to use premium vs mid-tier vs cheap models. Premium (Opus, o3, Gemini 3 Pro) only for complex reasoning, high-stakes, code review. Mid-tier (Sonnet, GPT-5.2) for most work. Fast (Haiku, GPT-5.4-mini, Gemini Flash, DeepSeek v3.2) for simple tasks. Grok for anything needing live web. o3/DeepSeek R1 for math and logic.

4. **Risk assessment rules** — high risk means output could cause financial, legal, or reputational harm if wrong. Medium means errors are recoverable. Low means casual/informational.

5. **Output schema** — strict JSON with the 8 fields. The classifier returns skill, model, industry, task_type, complexity, risk, depth, and reasoning.

**Safety fallbacks:** If the classifier picks an invalid skill key, it falls back to `generalist`. If it picks an invalid model key, it falls back to `claude-sonnet-4-6`. If the JSON is wrapped in markdown fences, they're stripped automatically.

**Why Haiku for classification:** It's the cheapest capable model (~$0.001 per classification). It doesn't need to be brilliant — it needs to read a prompt, match it against a menu, and output JSON. It does this reliably in ~2 seconds.

**Why the classifier picks the model (not hardcoded per skill):** This is a core design decision. If you hardcode "marketing_analyst always uses GPT-5.2", you lock in pricing and can't adapt to the specific request. A simple marketing question should use a cheap model. A complex competitive analysis should use a premium one. The classifier reasons about this per-request, optimizing cost and quality dynamically.

---

## The skill registry — 22 experts

**File:** `skills/registry.py`

The registry is a Python dictionary. Each key is a skill identifier, each value contains:

- **name** — human-readable label (e.g. "Startup Advisor")
- **tags** — list of keywords the classifier uses to match prompts to skills (e.g. ["strategy", "fundraising", "business model"])
- **system_prompt** — the full expert persona. This is NOT a generic instruction. Each skill has a specific methodology, named frameworks, explicit rules about what to do and what not to do, and a defined personality. These are 200-400 word prompts that read like briefing documents for a real specialist.
- **output_rules** — formatting instructions appended to the system prompt (e.g. "Diagnosis first. Framework second. Action third. No padding. Max 600 words.")
- **reviewer** — the key of another skill that reviews this skill's output, or None. This creates reviewer chains (startup_advisor is reviewed by marketing_analyst, financial_analyst is reviewed by startup_advisor, etc.)

### Skill inventory

**Business & Strategy (3 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Startup Advisor | `startup_advisor` | YC-partner-style advice. Focuses on real problems vs fake problems, beachhead customers, riskiest assumptions, next milestone. Direct and uncomfortable when needed. | marketing_analyst |
| Product Strategist | `product_strategist` | JTBD-driven product thinking. Pushes back on feature requests, builds roadmaps of bets not features, focuses on activation → retention → expansion. | startup_advisor |
| Decision Coach | `decision_coach` | Decision theory and behavioral economics. Clarifies the actual decision, surfaces alternatives, names cognitive biases, recommends decision processes. | None |

**Marketing & Sales (4 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Marketing Analyst | `marketing_analyst` | Funnel analysis, ICP clarity, conversion psychology. Leads with the single biggest lever. Cites principles by name (loss aversion, social proof, anchoring). | None |
| Sales Copywriter | `sales_copywriter` | Direct-response copywriting (Ogilvy/Sugarman style). Rewrites copy with psychological principles. Benefits over features, 7th-grade reading level, specific CTAs. | None |
| Growth Debugger | `growth_debugger` | Diagnoses metric drops and funnel anomalies. Thinks in hypotheses, not conclusions. Generates ranked hypotheses with evidence and recommends minimum experiments. | None |
| Customer Support Writer | `customer_support_writer` | Writes support responses ready to send. Acknowledges before explaining, clear next steps, matches customer energy. | None |

**Engineering (5 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Code Reviewer | `code_reviewer` | Staff-engineer-level review. Traffic light format (red/yellow/green). Prioritizes correctness → security → performance → reliability → maintainability. Includes corrected code. | debugging_engineer |
| Debugging Engineer | `debugging_engineer` | Root cause analysis. Reads errors literally, forms ranked hypotheses, provides copy-paste-ready fixes. Distinguishes data problems from code problems from environment problems. | None |
| Systems Architect | `systems_architect` | Distributed systems design. Starts with constraints, identifies hardest problem, chooses boring technology, designs for failure, data model first. ASCII diagrams when helpful. | None |
| Technical Writer | `technical_writer` | Documentation for developer tools and APIs. Show before tell, code examples first, clean Markdown, ready to publish. | None |
| DevOps & SRE | `devops_responder` | Incident response, runbooks, infrastructure diagnosis. Commands first, explanation second. Thinks in layers (DNS → network → LB → app → DB → cache). All commands copy-paste ready. | None |

**Legal & Finance (3 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Financial Analyst | `financial_analyst` | Startup financials and SaaS metrics. CAC, LTV, burn rate, runway, cohort analysis, P&L, valuation. Shows all math, flags every assumption, states confidence level. | startup_advisor |
| Legal Analyst | `legal_analyst` | Contract and legal concept analysis (NOT legal advice — always disclaims). Clause-by-clause analysis with risk ratings. Flags missing protections and unusual terms. | None |
| Risk Analyst | `risk_analyst` | Enterprise risk assessment. Full methodology: identification → classification → likelihood → impact → rating → controls → residual risk → recommendations. | legal_analyst |

**Research & Analysis (4 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Research Assistant | `research_assistant` | Rigorous research methodology. Distinguishes primary/secondary/inferred sources. TL;DR first, synthesis over lists, never fabricates statistics. | None |
| Market Researcher | `market_researcher` | Competitive intelligence, TAM analysis, ICP definition. Bottoms-up market sizing, real competitive alternatives including "do nothing". | None |
| Logic Checker | `logic_checker` | Identifies logical fallacies, unstated assumptions, internal contradictions, scope errors. Names every flaw, then steelmans the argument. | None |
| Trend Spotter | `trend_spotter` | Identifies emerging signals in tech, culture, and consumer behavior. Distinguishes signal vs noise, classifies as fad/trend/shift, gives business implications. | None |

**Creative (2 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Creative Writer | `creative_writer` | Versatile creative writing across brand voice, narrative, scripts, speeches. Finds the angle that makes a piece worth reading. Explains creative choices. | None |
| UX Critic | `ux_critic` | Product and UX critique. Evaluates clarity, friction, trust, hierarchy, consistency. Top 3 issues only, each with specific fix. No laundry lists. | None |

**General (2 skills)**

| Skill | Key | What it does | Reviewer |
|-------|-----|-------------|----------|
| Educator | `educator` | Explains any concept at any level. Starts with what the learner knows, uses analogies, layers complexity, concrete examples before abstract rules. | None |
| Generalist | `generalist` | Universal fallback. Answers directly, flags uncertainty, calibrates length to complexity. Used when no specialist fits. | None |

### How the classifier discovers skills

At import time, `registry.py` generates a `SKILL_MENU` string from the registry — one line per skill with key, name, and tags. This string is injected into the classifier's system prompt. When you add a skill to the registry dict, the classifier automatically sees it on the next request. No config files, no registration step.

---

## The adapter layer — 6 providers, 11 models

**Files:** `adapters/base.py`, `adapters/*_adapter.py`, `adapters/__init__.py`

Every provider gets a thin adapter class (~25 lines) that normalizes the provider's API to a single interface:

```python
class BaseAdapter(ABC):
    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> AdapterResponse:
        # Returns: text, model, input_tokens, output_tokens
```

### Provider adapters

| Adapter | Provider | SDK | Notes |
|---------|----------|-----|-------|
| `AnthropicAdapter` | Anthropic | `anthropic` | Native SDK. System prompt as separate parameter. |
| `OpenAIAdapter` | OpenAI | `openai` | Native SDK. System prompt as system message. |
| `GeminiAdapter` | Google | `google-genai` | Google GenAI SDK. System prompt as `system_instruction`. |
| `GrokAdapter` | xAI | `openai` | Uses OpenAI SDK with `base_url="https://api.x.ai/v1"`. OpenAI-compatible API. |
| `DeepSeekAdapter` | DeepSeek | `openai` | Uses OpenAI SDK with `base_url="https://api.deepseek.com"`. OpenAI-compatible API. |

**Key insight:** Grok and DeepSeek both expose OpenAI-compatible APIs. Their adapters are identical to the OpenAI adapter except for `base_url` and the API key env var. No extra SDK needed.

### Model registry

`adapters/__init__.py` contains `ADAPTER_MAP` — a dict mapping model key strings to adapter factory lambdas:

```python
ADAPTER_MAP = {
    "claude-opus-4-6":     lambda: AnthropicAdapter("claude-opus-4-6"),
    "claude-sonnet-4-6":   lambda: AnthropicAdapter("claude-sonnet-4-6"),
    "claude-haiku-4-5":    lambda: AnthropicAdapter("claude-haiku-4-5-20251001"),
    "gpt-5.2":             lambda: OpenAIAdapter("gpt-5.2"),
    "gpt-5.4-mini":        lambda: OpenAIAdapter("gpt-5.4-mini"),
    "o3":                  lambda: OpenAIAdapter("o3"),
    "gemini-3-pro":        lambda: GeminiAdapter("gemini-3-pro"),
    "gemini-2.5-flash":    lambda: GeminiAdapter("gemini-2.5-flash"),
    "grok-4.1":            lambda: GrokAdapter("grok-4-1"),
    "deepseek-v3.2":       lambda: DeepSeekAdapter("deepseek-chat"),
    "deepseek-r1":         lambda: DeepSeekAdapter("deepseek-reasoner"),
}
```

To add a model: one line here. To add a provider: one adapter file (~25 lines) + one import + lines here.

### Model tiers and when the classifier uses them

| Tier | Models | When used | Typical cost |
|------|--------|-----------|-------------|
| **Premium** | claude-opus-4-6, o3, gemini-3-pro | Complex reasoning, high-stakes analysis, code review, legal/financial risk | $0.02-0.08 per request |
| **Mid-tier** | claude-sonnet-4-6, gpt-5.2 | Most substantive work — the default sweet spot | $0.005-0.02 per request |
| **Fast/cheap** | claude-haiku-4-5, gpt-5.4-mini, gemini-2.5-flash, deepseek-v3.2 | Simple tasks, support drafts, quick questions | $0.0001-0.003 per request |
| **Reasoning** | o3, deepseek-r1 | Extended reasoning chains — math proofs, logic, complex risk analysis | $0.01-0.10 per request |
| **Web-enabled** | grok-4.1 | Tasks needing real-time web data, social signals, market intelligence | $0.0005-0.002 per request |

---

## The executor — execution + auto-review

**File:** `api/executor.py`

The executor does three things:

### 1. Primary execution

- Looks up the skill from the registry (gets system_prompt + output_rules)
- Gets the adapter for the classifier's chosen model via `get_adapter()`
- Enriches the user's prompt with classifier context: `[Context: industry=saas, task=advise, complexity=high, depth=deep]`
- Calls the model through the adapter
- Tracks token counts and calculates cost

### 2. Automatic fallback

If the chosen model fails (provider down, auth error, rate limit, timeout), the executor catches the exception and retries with `claude-sonnet-4-6` as a universal fallback. The user always gets an answer, even if their preferred provider is having a bad day.

### 3. Auto-review (the "second opinion")

The review triggers when ANY of these conditions are true:
- `risk == "high"` — output could cause financial, legal, or reputational harm
- `complexity == "high"` — requires multi-step reasoning or deep domain expertise
- `risk == "medium" AND depth == "deep"` — moderate stakes but user needs exhaustive analysis

When triggered:
1. The primary skill's designated `reviewer` field points to another skill key
2. The reviewer skill's system prompt is loaded
3. The reviewer receives BOTH the original prompt AND the primary answer
4. The reviewer is instructed to: "Correct errors, strengthen weak points, return the best possible final answer"
5. The reviewer always runs on `claude-opus-4-6` (premium model for the premium pass)
6. The final answer is the reviewer's output, not the primary output

**Reviewer chains** — each skill can designate a different reviewer, creating cross-domain validation:
- `startup_advisor` → reviewed by `marketing_analyst` (business + market perspective)
- `financial_analyst` → reviewed by `startup_advisor` (numbers + strategy perspective)
- `code_reviewer` → reviewed by `debugging_engineer` (review + implementation perspective)
- `risk_analyst` → reviewed by `legal_analyst` (risk + legal perspective)
- `product_strategist` → reviewed by `startup_advisor` (product + business perspective)

Skills without a reviewer (e.g. `generalist`, `educator`, `debugging_engineer`) skip the review pass even if risk is high.

---

## The API layer

**File:** `api/main.py`

FastAPI app with three endpoints:

- `POST /v1/ask` — the main endpoint. Takes a prompt, returns the full response with answer, skill, model, review status, cost, and classifier output.
- `GET /v1/skills` — lists all available skills with names, tags, and reviewer chains. Useful for building UIs or debugging routing.
- `GET /health` — returns `{"status": "ok"}`.

**Authentication:** API key via `X-Api-Key` header or `api_key` field in the request body. Valid keys are loaded from the `API_KEYS` environment variable (comma-separated).

**File:** `api/models.py`

Pydantic schemas:
- `AskRequest` — prompt (required), api_key (optional)
- `ClassifierOutput` — skill, model, industry, task_type, complexity, risk, depth, reasoning
- `AskResponse` — answer, skill_used, model_used, reviewed, cost_usd, classifier

---

## The SDK

**File:** `sdk/client.py`

Python client for the API. Wraps httpx with typed dataclasses:

```python
from sdk import AskAI

# Initialize
client = AskAI(api_key="your-key", base_url="http://localhost:8000")

# Ask a question
result = client.ask("your prompt here")

# Access everything
result.answer           # the expert's response
result.skill_used       # "Marketing Analyst"
result.model_used       # "gpt-5.2" or "claude-opus-4-6 -> claude-opus-4-6" if reviewed
result.reviewed         # True/False
result.cost_usd         # 0.0123
result.classifier.skill      # "marketing_analyst"
result.classifier.model      # "gpt-5.2"
result.classifier.industry   # "marketing"
result.classifier.task_type  # "analysis"
result.classifier.complexity # "medium"
result.classifier.risk       # "low"
result.classifier.depth      # "standard"
result.classifier.reasoning  # "Marketing funnel analysis, mid-tier model sufficient"

# List all skills
skills = client.skills()

# Context manager
with AskAI(api_key="key", base_url="http://localhost:8000") as client:
    result = client.ask("...")
```

---

## Cost tracking

**File:** `skills/pricing.py`

Every model has pricing data (input cost per 1M tokens, output cost per 1M tokens). The `estimate_cost()` function calculates the exact cost of each API call from token counts. Every response includes `cost_usd` — the total cost of that request including both primary and reviewer passes.

This means you can:
- Track cost per request in your logs
- Calculate daily/monthly spend
- See exactly which models and skills cost the most
- Build usage dashboards on top of the data

---

## Logging — full thought process

The server logs every step of every request so you can watch the system think:

```
22:18:43 askai.main       NEW REQUEST: Should we take the $4M SAFE...
22:18:43 askai.classifier ============================================================
22:18:43 askai.classifier CLASSIFYING: Should we take the $4M SAFE...
22:18:45 askai.classifier CLASSIFIER RAW: {"skill":"startup_advisor","model":"claude-opus-4-6"...}
22:18:45 askai.classifier DECISION: skill=startup_advisor | model=claude-opus-4-6 | saas/advise | complexity=high risk=high depth=deep
22:18:45 askai.classifier REASONING: High-stakes fundraising decision requires nuanced reasoning...
22:18:45 askai.executor   EXECUTING: skill=startup_advisor (Startup Advisor) on model=claude-opus-4-6
22:19:15 askai.executor     MODEL claude-opus-4-6 responded in 30.5s (342 in / 981 out tokens)
22:19:15 askai.executor     PRIMARY COST: $0.026235
22:19:15 askai.executor     REVIEW TRIGGERED: risk=high complexity=high depth=deep
22:19:15 askai.executor     REVIEWING with skill=marketing_analyst (Marketing Analyst)
22:20:05 askai.executor     MODEL claude-opus-4-6 responded in 50.4s (1262 in / 2048 out tokens)
22:20:05 askai.executor     REVIEW COST: $0.057510
22:20:05 askai.executor   TOTAL COST: $0.083745 | reviewed=True
22:20:05 askai.executor   ANSWER PREVIEW: The single biggest issue with this pricing page...
22:20:05 askai.main       REQUEST COMPLETE in 82.5s | cost=$0.083745 reviewed=True
```

Logged per request: prompt preview, classifier's raw JSON, routing decision with reasoning, model used, response time, token counts, cost breakdown (primary + review), whether review triggered and why, answer preview, total time.

If a model fails and falls back, that's logged too:
```
askai.executor   MODEL gpt-5.2 FAILED: AuthenticationError — falling back to claude-sonnet-4-6
askai.executor   FALLBACK claude-sonnet-4-6 responded in 4.2s (...)
```

---

## Project structure

```
askai/                              ~1,300 lines total
│
├── adapters/                       Provider adapters (one per company)
│   ├── base.py                       BaseAdapter ABC + AdapterResponse dataclass
│   ├── anthropic_adapter.py          Anthropic (Claude) — native SDK
│   ├── openai_adapter.py            OpenAI (GPT, o3) — native SDK
│   ├── gemini_adapter.py            Google (Gemini) — google-genai SDK
│   ├── grok_adapter.py              xAI (Grok) — OpenAI SDK + custom base_url
│   ├── deepseek_adapter.py          DeepSeek — OpenAI SDK + custom base_url
│   └── __init__.py                  ADAPTER_MAP: model key → adapter factory
│
├── skills/                         Expert knowledge layer
│   ├── registry.py                  22 skill definitions (persona + prompt + rules + tags)
│   ├── pricing.py                   Model pricing data + cost estimation
│   └── __init__.py                  Exports
│
├── api/                            FastAPI backend
│   ├── models.py                    Pydantic schemas (AskRequest, ClassifierOutput, AskResponse)
│   ├── classifier.py                The brain — one Haiku call → skill + model + metadata
│   ├── executor.py                  Runs skill on model, auto-review, fallback
│   ├── main.py                      /v1/ask endpoint, auth, logging
│   └── __init__.py
│
├── sdk/                            Python client library
│   ├── client.py                    AskAI class with typed Result/ClassifierResult
│   └── __init__.py                  Exports
│
├── tests/
│   └── test_registry.py            Registry + adapter sanity checks
│
├── demo.py                         6 demo prompts across different skills/providers
├── .env                            API keys for all 5 providers (gitignored)
├── .env.example                    Template for .env
├── .gitignore                      Excludes .env, __pycache__, .venv
└── requirements.txt                fastapi, uvicorn, anthropic, openai, google-genai, httpx, pydantic, python-dotenv
```

---

## How to extend

### Add a new skill

Add one dict entry to `REGISTRY` in `skills/registry.py`:

```python
"my_new_skill": {
    "name": "My New Skill",
    "tags": ["keyword1", "keyword2", "keyword3"],
    "reviewer": None,  # or another skill key like "startup_advisor"
    "system_prompt": """Your expert persona and methodology here...""",
    "output_rules": "Your formatting rules here.",
},
```

That's it. The classifier will discover it automatically from the skill menu on the next request.

### Add a new model

Add one line to `ADAPTER_MAP` in `adapters/__init__.py`:

```python
"new-model-name": lambda: ExistingAdapter("actual-api-model-id"),
```

If it's an OpenAI-compatible API (like Grok and DeepSeek), just use `OpenAIAdapter` with a custom base_url. If it needs a new SDK, create a new adapter file (~25 lines).

### Add a new provider

1. Create `adapters/newprovider_adapter.py` (~25 lines — implement `complete()`)
2. Import it in `adapters/__init__.py`
3. Add model entries to `ADAPTER_MAP`
4. Add the API key env var to `.env`

### Change routing logic

Edit the classifier prompt in `api/classifier.py`. The `_build_classifier_prompt()` function contains the model selection guidelines and the output schema. Change what the classifier optimizes for.

### Change review logic

Edit `_should_review()` in `api/executor.py`. Currently triggers on: risk=high OR complexity=high OR (risk=medium AND depth=deep). Change the conditions to match your needs.

### Change which model the reviewer uses

Edit the `reviewer_model` variable in `api/executor.py`. Currently hardcoded to `claude-opus-4-6`. Could be made dynamic (e.g. let the classifier pick the reviewer model too).

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/HighForceAI/ask.ai.git
cd ask.ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API keys
cp .env.example .env
# Edit .env — you need at minimum ANTHROPIC_API_KEY (for the classifier)
# Add OPENAI_API_KEY, GEMINI_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY for full coverage
# The system falls back gracefully if a provider key is missing

# 4. Run the server
PYTHONPATH=. uvicorn api.main:app --reload

# 5. Test it
PYTHONPATH=. python3 demo.py

# Or hit it directly
curl -X POST http://localhost:8000/v1/ask \
  -H "X-Api-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Review this NDA clause: perpetual non-compete"}'
```

---

## API reference

### POST /v1/ask

Send a prompt, get an expert answer.

**Request:**
```json
{
  "prompt": "Your question here"
}
```

**Headers:** `X-Api-Key: your-api-key`

**Response:**
```json
{
  "answer": "The full expert answer...",
  "skill_used": "Legal Analyst",
  "model_used": "claude-opus-4-6",
  "reviewed": false,
  "cost_usd": 0.0312,
  "classifier": {
    "skill": "legal_analyst",
    "model": "claude-opus-4-6",
    "industry": "legal",
    "task_type": "review",
    "complexity": "medium",
    "risk": "high",
    "depth": "standard",
    "reasoning": "Legal contract review with potential enforceability issues requires premium reasoning model"
  }
}
```

### GET /v1/skills

List all available skills.

**Response:**
```json
{
  "startup_advisor": {
    "name": "Startup Advisor",
    "tags": ["strategy", "fundraising", "business model", "pitch", "startup"],
    "reviewer": "marketing_analyst"
  },
  ...
}
```

### GET /health

**Response:** `{"status": "ok"}`

---

## Design decisions

**Why no routing table?** A routing table is a maintenance burden. Every time you add a skill, you'd need to update routing rules. The classifier LLM already understands natural language — it can read the skill menu and reason about the best match. This is simpler and more flexible than any rule-based system.

**Why the classifier picks the model too?** If you hardcode "financial_analyst always uses Gemini", you can't distinguish between a simple revenue question (use a cheap model) and a complex valuation analysis (use a premium model). The classifier sees the actual prompt and reasons about the right model for THIS specific request.

**Why Haiku for classification?** Classification is a simple task: read a prompt, pick from a menu, output JSON. Haiku does this reliably for ~$0.001. Using a smarter model for routing would add cost and latency with no quality improvement.

**Why Opus for reviews?** The review pass is the "second opinion" — it's the quality guarantee. It only triggers on high-stakes requests where getting it wrong matters. Using the best available model for this pass is worth the cost because it's the last line of defense.

**Why no LangChain/CrewAI/etc?** The entire pipeline is: one LLM call to classify, one LLM call to execute, optionally one more to review. That's 2-3 API calls orchestrated by a few Python functions. A framework would add thousands of lines of abstraction for no benefit. Every line of code in this project does something you can see and understand.

**Why provider adapters instead of a unified SDK?** Each provider has different quirks (Anthropic uses a separate system parameter, OpenAI uses a system message, Gemini uses system_instruction, Grok/DeepSeek use OpenAI's format with a different base_url). A 25-line adapter per provider is simpler and more reliable than trying to unify them behind a third-party abstraction.

**Why not async all the way?** The adapters use sync SDK clients called from async endpoint handlers. This works fine for a single-request API. True async would matter at high concurrency — it's a straightforward upgrade (swap sync clients for async clients) when needed.

---

## Why this exists

Every AI API gives you one model, one personality, one answer. But different questions need different experts and different models. A fundraising decision needs a different brain than a code review. A market research question benefits from real-time web access that a legal analysis doesn't need. A simple support reply doesn't need a $25/M-token model.

ask.ai is the routing layer that makes this automatic. One API endpoint, 22 experts, 11 models, 6 providers, optimal cost — and a built-in second opinion for anything high-stakes.

The architecture is the product: **classify → route → execute → review**. No frameworks, no abstractions, no dependencies beyond the provider SDKs. Every file is short, every piece is swappable, and the whole system is understandable in 10 minutes.

# ask.ai

One prompt in, one expert answer out. Multi-model, multi-provider AI that picks the right expert and the right model for every question.

## What it does

You send a question. The system:

1. **Classifies** your prompt (2 seconds, pennies) — figures out the domain, task type, complexity, risk level, and depth needed
2. **Picks the best expert** from 22 specialist skills (startup advisor, code reviewer, financial analyst, etc.)
3. **Picks the best model** from 11 models across 6 providers (Anthropic, OpenAI, Google, xAI, DeepSeek) — not hardcoded, the classifier reasons about which model fits THIS specific request
4. **Executes** the expert skill against the chosen model
5. **Reviews** automatically if the request is high-risk or high-complexity — a second expert checks and strengthens the answer using a premium model

You get back: the answer, which skill was used, which model(s), whether it was reviewed, and the cost.

```python
from sdk import AskAI

client = AskAI(api_key="dev-key-123", base_url="http://localhost:8000")
result = client.ask("Should we take the $4M SAFE at $20M cap or wait for revenue?")

print(result.answer)       # the expert answer
print(result.skill_used)   # "Startup Advisor"
print(result.model_used)   # "claude-opus-4-6 -> claude-opus-4-6"
print(result.reviewed)     # True (high-risk triggered auto-review)
print(result.cost_usd)     # $0.0837
```

## How it thinks

```
User prompt
    │
    ▼
┌─────────────────────────────────┐
│  CLASSIFIER (Haiku — fast/cheap)│
│  Picks: skill + model + metadata│
│  industry, task, complexity,    │
│  risk, depth, reasoning         │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  EXECUTOR                       │
│  Runs skill prompt on chosen    │
│  model from any provider        │
│                                 │
│  if risk=high or complexity=high│
│  ┌────────────────────────────┐ │
│  │ REVIEWER (Opus)            │ │
│  │ Second expert checks and   │ │
│  │ strengthens the answer     │ │
│  └────────────────────────────┘ │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  RESPONSE                       │
│  answer + skill + model + cost  │
│  + reviewed flag + classifier   │
└─────────────────────────────────┘
```

The key insight: **no routing table**. The classifier LLM decides which skill AND which model is best for every request. A pricing page review gets routed to the Marketing Analyst on GPT-5.2 (strong at business writing). A fundraising decision gets routed to the Startup Advisor on Opus (nuanced reasoning). A quick support reply gets routed to the Support Writer on Haiku (fast, cheap). The system reasons about cost/quality tradeoffs on every single request.

## The 22 skills

| Domain | Skills |
|--------|--------|
| **Business & Strategy** | Startup Advisor, Product Strategist, Decision Coach |
| **Marketing & Sales** | Marketing Analyst, Sales Copywriter, Growth Debugger, Customer Support Writer |
| **Engineering** | Code Reviewer, Debugging Engineer, Systems Architect, Technical Writer, DevOps & SRE |
| **Legal & Finance** | Financial Analyst, Legal Analyst, Risk Analyst |
| **Research & Analysis** | Research Assistant, Market Researcher, Logic Checker, Trend Spotter |
| **Creative** | Creative Writer, UX Critic |
| **General** | Educator, Generalist (fallback) |

Each skill is a full expert persona with methodology, frameworks, and output formatting rules. Not generic prompts — these are opinionated specialists.

## The 11 models across 6 providers

| Provider | Models | Best at |
|----------|--------|---------|
| **Anthropic** | Opus 4.6, Sonnet 4.6, Haiku 4.5 | Coding, reasoning, instruction following, classification |
| **OpenAI** | GPT-5.2, GPT-5.4-mini, o3 | Creative writing, business content, math/logic reasoning |
| **Google** | Gemini 3 Pro, Gemini 2.5 Flash | Data analysis, long documents, cheapest capable model |
| **xAI** | Grok 4.1 | Real-time web search, social signals, market intelligence |
| **DeepSeek** | v3.2, R1 | Best value overall, budget reasoning |

The classifier picks the right model for each request. Premium models (Opus, o3) only get used when the task genuinely requires it. Simple questions get fast/cheap models. The system optimizes cost automatically.

## Auto-review

When risk is high or complexity is high, the system automatically runs a second pass:

1. Primary expert writes the answer
2. A different expert (the skill's designated reviewer) checks the answer on a premium model
3. The reviewer corrects errors, strengthens weak points, and returns the final answer

This is the "second opinion" — two different expert perspectives synthesized into one answer. It only triggers when it matters, so most requests stay fast and cheap.

## Project structure

```
askai/                          1,322 lines total
├── adapters/                   adapter per provider (add a model = 1 line)
│   ├── base.py                   abstract interface
│   ├── anthropic_adapter.py      Anthropic (Claude)
│   ├── openai_adapter.py         OpenAI (GPT, o3)
│   ├── gemini_adapter.py         Google (Gemini)
│   ├── grok_adapter.py           xAI (Grok)
│   ├── deepseek_adapter.py       DeepSeek
│   └── __init__.py               ADAPTER_MAP — model key → factory
├── skills/                     expert personas + pricing
│   ├── registry.py               22 skills with full prompts (add a skill = 1 dict)
│   └── pricing.py                model pricing for cost tracking
├── api/                        FastAPI backend
│   ├── models.py                 Pydantic schemas
│   ├── classifier.py             the brain — picks skill + model
│   ├── executor.py               runs skill, optional review, fallback
│   └── main.py                   /v1/ask endpoint + auth
├── sdk/                        Python client
│   └── client.py                 AskAI class — client.ask("...")
├── tests/
│   └── test_registry.py         registry + adapter sanity checks
├── demo.py                     6 demo prompts across different skills
├── .env                        API keys (all 5 providers)
└── requirements.txt
```

Every file does one thing. Every file is short. To customize:

- **Add a skill:** one dict entry in `skills/registry.py`
- **Add a model:** one line in `adapters/__init__.py`
- **Add a provider:** one adapter file (~25 lines), one import
- **Tweak a prompt:** edit the string in the registry
- **Change routing logic:** edit `classifier.py`
- **Change review logic:** edit `_should_review()` in `executor.py`

## Quickstart

```bash
# 1. Clone and install
cd askai
pip install -r requirements.txt

# 2. Add your API keys
cp .env.example .env
# Edit .env with your keys for: Anthropic, OpenAI, Google, xAI, DeepSeek

# 3. Run the server
PYTHONPATH=. uvicorn api.main:app --reload

# 4. Test it
PYTHONPATH=. python3 demo.py
```

## API

### POST /v1/ask

```bash
curl -X POST http://localhost:8000/v1/ask \
  -H "X-Api-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Review this NDA clause: perpetual non-compete"}'
```

Response:
```json
{
  "answer": "...",
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
    "reasoning": "Legal contract review with potential enforceability issues..."
  }
}
```

### GET /v1/skills

Lists all available skills with their tags and reviewer chains.

### GET /health

Returns `{"status": "ok"}`.

## Logging

The server logs the full thought process for every request:

```
22:18:43 askai.main       NEW REQUEST: Should we take the $4M SAFE...
22:18:43 askai.classifier ============================================================
22:18:43 askai.classifier CLASSIFYING: Should we take the $4M SAFE...
22:18:45 askai.classifier CLASSIFIER RAW: {"skill":"startup_advisor","model":"claude-opus-4-6"...}
22:18:45 askai.classifier DECISION: skill=startup_advisor | model=claude-opus-4-6 | saas/advise | complexity=high risk=high depth=deep
22:18:45 askai.classifier REASONING: High-stakes fundraising decision...
22:18:45 askai.executor   EXECUTING: skill=startup_advisor (Startup Advisor) on model=claude-opus-4-6
22:19:15 askai.executor     MODEL claude-opus-4-6 responded in 30.5s (342 in / 981 out tokens)
22:19:15 askai.executor     PRIMARY COST: $0.026235
22:19:15 askai.executor     REVIEW TRIGGERED: risk=high complexity=high depth=deep
22:19:15 askai.executor     REVIEWING with skill=marketing_analyst (Marketing Analyst)
22:20:05 askai.executor     MODEL claude-opus-4-6 responded in 50.4s (1262 in / 2048 out tokens)
22:20:05 askai.executor     REVIEW COST: $0.057510
22:20:05 askai.executor   TOTAL COST: $0.083745 | reviewed=True
22:20:05 askai.main       REQUEST COMPLETE in 82.5s | cost=$0.083745 reviewed=True
```

## Cost

The system optimizes cost automatically. Simple questions cost fractions of a cent. Complex reviewed answers cost ~$0.05-0.10. The classifier picks cheap models for easy tasks and premium models only when needed. Every response includes the exact cost.

"""
Model pricing reference — used for cost tracking and smart model selection.
Update when providers change pricing.
"""

MODEL_PRICING = {
    # Anthropic
    "claude-opus-4-6": {
        "provider": "Anthropic",
        "input_per_1m": 5.00,
        "output_per_1m": 25.00,
        "tier": "premium",
        "best_at": ["coding", "nuanced reasoning", "regulated industries", "long-context"],
    },
    "claude-sonnet-4-6": {
        "provider": "Anthropic",
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
        "tier": "mid",
        "best_at": ["instruction following", "structured output", "general workhorse"],
    },
    "claude-haiku-4-5": {
        "provider": "Anthropic",
        "input_per_1m": 1.00,
        "output_per_1m": 5.00,
        "tier": "fast",
        "best_at": ["classification", "support", "high-volume simple tasks"],
    },
    # OpenAI
    "gpt-5.2": {
        "provider": "OpenAI",
        "input_per_1m": 1.75,
        "output_per_1m": 14.00,
        "tier": "mid",
        "best_at": ["creative writing", "business writing", "instruction following"],
    },
    "gpt-5.4-mini": {
        "provider": "OpenAI",
        "input_per_1m": 0.75,
        "output_per_1m": 3.00,
        "tier": "fast",
        "best_at": ["speed", "simple tasks", "high-volume"],
    },
    "o3": {
        "provider": "OpenAI",
        "input_per_1m": 10.00,
        "output_per_1m": 40.00,
        "tier": "reasoning-premium",
        "best_at": ["hard math", "multi-step reasoning", "logic", "science"],
    },
    # Google
    "gemini-3-pro": {
        "provider": "Google",
        "input_per_1m": 2.00,
        "output_per_1m": 12.00,
        "tier": "premium",
        "best_at": ["math", "data analysis", "long documents", "multimodal"],
    },
    "gemini-2.5-flash": {
        "provider": "Google",
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "tier": "fast",
        "best_at": ["cheapest capable model", "long-context budget", "prototyping"],
    },
    # xAI
    "grok-4.1": {
        "provider": "xAI",
        "input_per_1m": 0.20,
        "output_per_1m": 0.50,
        "tier": "fast",
        "best_at": ["real-time web", "social signals", "market intelligence", "trends"],
    },
    # DeepSeek
    "deepseek-v3.2": {
        "provider": "DeepSeek",
        "input_per_1m": 0.28,
        "output_per_1m": 0.42,
        "tier": "fast",
        "best_at": ["best value overall", "general tasks", "fallback"],
    },
    "deepseek-r1": {
        "provider": "DeepSeek",
        "input_per_1m": 0.55,
        "output_per_1m": 2.19,
        "tier": "reasoning-mid",
        "best_at": ["reasoning", "math", "logic", "budget o3 alternative"],
    },
}


def estimate_cost(model_key: str, input_tokens: int, output_tokens: int) -> float:
    """Returns estimated cost in USD."""
    p = MODEL_PRICING[model_key]
    return (input_tokens / 1_000_000 * p["input_per_1m"]) + (
        output_tokens / 1_000_000 * p["output_per_1m"]
    )

from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter
from .gemini_adapter import GeminiAdapter
from .grok_adapter import GrokAdapter
from .deepseek_adapter import DeepSeekAdapter
from .base import AdapterResponse

# model key -> adapter factory
# Add new models here. That's it.
ADAPTER_MAP = {
    # Anthropic
    "claude-opus-4-6": lambda: AnthropicAdapter("claude-opus-4-6"),
    "claude-sonnet-4-6": lambda: AnthropicAdapter("claude-sonnet-4-6"),
    "claude-haiku-4-5": lambda: AnthropicAdapter("claude-haiku-4-5-20251001"),
    # OpenAI
    "gpt-5.2": lambda: OpenAIAdapter("gpt-5.2"),
    "gpt-5.4-mini": lambda: OpenAIAdapter("gpt-5.4-mini"),
    "o3": lambda: OpenAIAdapter("o3"),
    # Google
    "gemini-3-pro": lambda: GeminiAdapter("gemini-3-pro"),
    "gemini-2.5-flash": lambda: GeminiAdapter("gemini-2.5-flash"),
    # xAI
    "grok-4.1": lambda: GrokAdapter("grok-4-1"),
    # DeepSeek
    "deepseek-v3.2": lambda: DeepSeekAdapter("deepseek-chat"),
    "deepseek-r1": lambda: DeepSeekAdapter("deepseek-reasoner"),
}

VALID_MODELS = set(ADAPTER_MAP.keys())


def get_adapter(model_key: str):
    if model_key not in ADAPTER_MAP:
        raise ValueError(f"Unknown model: {model_key}. Valid: {sorted(VALID_MODELS)}")
    return ADAPTER_MAP[model_key]()

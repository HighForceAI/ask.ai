from pydantic import BaseModel
from typing import Optional, Literal


class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class AskRequest(BaseModel):
    prompt: str
    api_key: Optional[str] = None
    history: list[ChatMessage] = []  # previous messages for context


class ClassifierOutput(BaseModel):
    """The classifier decides everything in one shot."""
    skill: str                                          # key from REGISTRY
    model: str                                          # key from ADAPTER_MAP
    industry: str                                       # e.g. "saas", "legal", "finance"
    task_type: str                                      # e.g. "analysis", "writing", "debugging"
    complexity: Literal["low", "medium", "high"]
    risk: Literal["low", "medium", "high"]
    depth: Literal["quick", "standard", "deep"]
    reasoning: str                                      # one-line explanation of choices


class AskResponse(BaseModel):
    answer: str
    skill_used: str
    model_used: str
    reviewed: bool
    cost_usd: float
    classifier: ClassifierOutput

"""
ask.ai Python SDK

Usage:
    from sdk import AskAI

    client = AskAI(api_key="dev-key-123", base_url="http://localhost:8000")
    result = client.ask("Review this SaaS pricing page")
    print(result.answer)
"""

import httpx
from dataclasses import dataclass


@dataclass
class ClassifierResult:
    skill: str
    model: str
    industry: str
    task_type: str
    complexity: str
    risk: str
    depth: str
    reasoning: str


@dataclass
class Result:
    answer: str
    skill_used: str
    model_used: str
    reviewed: bool
    cost_usd: float
    classifier: ClassifierResult

    def __repr__(self):
        flag = " [reviewed]" if self.reviewed else ""
        return f"<Result skill={self.skill_used} model={self.model_used}{flag} ${self.cost_usd:.4f}>"


class AskAI:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.ask.ai",
        timeout: int = 120,
    ):
        self.client = httpx.Client(
            headers={"X-Api-Key": api_key},
            timeout=timeout,
        )
        self.base_url = base_url.rstrip("/")

    def ask(self, prompt: str) -> Result:
        """Send a prompt, get an expert answer back."""
        resp = self.client.post(
            f"{self.base_url}/v1/ask",
            json={"prompt": prompt},
        )
        resp.raise_for_status()
        data = resp.json()
        return Result(
            answer=data["answer"],
            skill_used=data["skill_used"],
            model_used=data["model_used"],
            reviewed=data["reviewed"],
            cost_usd=data["cost_usd"],
            classifier=ClassifierResult(**data["classifier"]),
        )

    def skills(self) -> dict:
        """List all available skills."""
        resp = self.client.get(f"{self.base_url}/v1/skills")
        resp.raise_for_status()
        return resp.json()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

import os
import anthropic
from .base import BaseAdapter, AdapterResponse


class AnthropicAdapter(BaseAdapter):
    def __init__(self, model: str):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model

    async def complete(
        self, system: str, user: str, max_tokens: int = 2048
    ) -> AdapterResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return AdapterResponse(
            text=response.content[0].text,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

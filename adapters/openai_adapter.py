from openai import OpenAI
from .base import BaseAdapter, AdapterResponse


class OpenAIAdapter(BaseAdapter):
    def __init__(self, model: str):
        self.client = OpenAI()
        self.model = model

    async def complete(
        self, system: str, user: str, max_tokens: int = 2048
    ) -> AdapterResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return AdapterResponse(
            text=response.choices[0].message.content,
            model=self.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

import os
from google import genai
from .base import BaseAdapter, AdapterResponse


class GeminiAdapter(BaseAdapter):
    def __init__(self, model: str):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model_name = model

    async def complete(
        self, system: str, user: str, max_tokens: int = 2048
    ) -> AdapterResponse:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=user,
            config={
                "system_instruction": system,
                "max_output_tokens": max_tokens,
            },
        )
        return AdapterResponse(
            text=response.text,
            model=self.model_name,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )

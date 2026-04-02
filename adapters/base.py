from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AdapterResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class BaseAdapter(ABC):
    @abstractmethod
    async def complete(
        self, system: str, user: str, max_tokens: int = 2048
    ) -> AdapterResponse:
        pass

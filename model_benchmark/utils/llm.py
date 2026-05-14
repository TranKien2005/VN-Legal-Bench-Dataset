import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from model_benchmark.utils.paths import PROJECT_ROOT


load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class LLMResult:
    content: str
    latency_sec: float


class RouterLLMClient:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL")
        self.api_key = os.getenv("NINEROUTER_API_KEY", "")
        self.base_url = os.getenv("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
        if not self.model:
            raise ValueError("Set BENCHMARK_MODEL or LLM_MODEL in .env/environment")
        if not self.api_key:
            raise ValueError("Set NINEROUTER_API_KEY in .env/environment")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful legal assistant expert in Vietnamese law.",
        temperature: float = 0.0,
    ) -> LLMResult:
        started = time.perf_counter()
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        latency = time.perf_counter() - started
        content = completion.choices[0].message.content or ""
        return LLMResult(content=content.strip(), latency_sec=latency)

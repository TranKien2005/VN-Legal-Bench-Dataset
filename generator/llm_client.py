import os
from openai import OpenAI
from config.settings import settings

class LLMClient:
    def __init__(self, model: str = "llama3"):
        self.api_key = settings.NINEROUTER_API_KEY
        self.base_url = settings.NINEROUTER_BASE_URL
        
        if not self.api_key:
            raise ValueError("NINEROUTER_API_KEY not found in settings/.env")
        
        # 9router is OpenAI-compatible
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.model = model

    def generate(self, prompt: str, system_prompt: str = "You are a helpful legal assistant expert in Vietnamese law.") -> str:
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                temperature=0.1,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error calling 9router: {e}")
            return ""

"""AI HTTP client for OpenAI-compatible APIs"""

import json
from typing import Optional

import httpx


class AIClient:
    """Client for OpenAI-compatible APIs"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip('/')

    async def chat(self, messages: list, temperature: float = 0.1) -> str:
        """Send chat request and get response text"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature
                }
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content'].strip()

    async def test_connection(self) -> bool:
        """Test API connection and authentication"""
        try:
            await self.chat([{"role": "user", "content": "Hi"}])
            return True
        except Exception:
            return False

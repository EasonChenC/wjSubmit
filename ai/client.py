"""AI HTTP client using OpenAI SDK for better compatibility"""

from typing import Optional
from openai import AsyncOpenAI


class AIClient:
    """Client for OpenAI-compatible APIs using OpenAI SDK

    Works with:
    - OpenAI (gpt-4, gpt-4o-mini, etc.)
    - DeepSeek (deepseek-v4-pro, deepseek-v4-flash, etc.)
    - Other OpenAI-compatible services
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip('/')

        # Initialize AsyncOpenAI client for async support
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    async def chat(self, messages: list, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        """Send chat request and get response text

        Uses AsyncOpenAI SDK which handles all protocol details correctly.
        Extracts ONLY the 'content' field, NOT the 'reasoning_content' (thinking process).

        Disables "thinking" mode via extra_body so reasoning models (e.g.
        DeepSeek-Reasoner) don't spend the token budget on reasoning_content
        before writing the final content — which previously could leave
        content empty for large inputs (e.g. many questions to analyze).
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                extra_body={"thinking": {"type": "disabled"}}
            )

            # Extract ONLY the final content, not reasoning_content
            if response.choices and len(response.choices) > 0:
                message = response.choices[0].message

                # Explicitly get 'content' field (the final answer)
                # Ignore 'reasoning_content' (the thinking process)
                content = message.content

                if content:
                    return content.strip()
                else:
                    raise ValueError("No content in response message")
            else:
                raise ValueError("No choices in response")

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

    async def test_connection(self) -> bool:
        """Test API connection and authentication"""
        try:
            result = await self.chat([{"role": "user", "content": "Hi"}])
            print(f"Connection test successful, response: {result[:50]}...")
            return True
        except Exception as e:
            import sys
            print(f"Connection test failed: {e}", file=sys.stderr)
            return False

import httpx
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class LLMResponse(BaseModel):
    content: str
    raw: Optional[Dict[str, Any]] = None

class LLMClient:
    def __init__(self, base_url: str = "http://localhost:11434", provider: str = "ollama"):
        self.base_url = base_url
        self.provider = provider

    async def chat(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7) -> LLMResponse:
        if self.provider == "ollama":
            return await self._chat_ollama(model, messages, temperature)
        elif self.provider == "lm_studio":
            return await self._chat_openai_compatible(model, messages, temperature)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def stream_chat(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7):
        if self.provider == "ollama":
            async for chunk in self._stream_ollama(model, messages, temperature):
                yield chunk
        elif self.provider == "lm_studio":
            async for chunk in self._stream_openai_compatible(model, messages, temperature):
                yield chunk
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _chat_ollama(self, model: str, messages: List[Dict[str, str]], temperature: float) -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return LLMResponse(content=data["message"]["content"], raw=data)

    async def _stream_ollama(self, model: str, messages: List[Dict[str, str]], temperature: float):
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature}
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                    if data.get("done"):
                        break

    async def _chat_openai_compatible(self, model: str, messages: List[Dict[str, str]], temperature: float) -> LLMResponse:
        # For LM Studio or local OpenAI-compatible APIs
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return LLMResponse(content=data["choices"][0]["message"]["content"], raw=data)

    async def _stream_openai_compatible(self, model: str, messages: List[Dict[str, str]], temperature: float):
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    if line.strip() == "data: [DONE]":
                        break
                    data = json.loads(line[6:])
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0].get("delta", {}).get("content")
                        if content:
                            yield content

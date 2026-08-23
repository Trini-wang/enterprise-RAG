import json
import os
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from app.models import AIModel, ModelProvider


class ProviderError(RuntimeError):
    def __init__(self, message: str, code: str = "MODEL_UPSTREAM_ERROR") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class CompletionResult:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class OpenAICompatibleProvider:
    def __init__(self, provider: ModelProvider, model: AIModel) -> None:
        self.provider = provider
        self.model = model
        self.api_key = getattr(provider, "_resolved_api_key", None) or os.getenv(provider.api_key_env, "")
        self.url = f"{provider.base_url.rstrip('/')}/chat/completions"

    def _payload(self, messages: list[dict[str, str]], temperature: float, max_tokens: int, stream: bool) -> dict:
        payload = {
            "model": self.model.model_key, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        codes = {401: "MODEL_AUTH_FAILED", 403: "MODEL_AUTH_FAILED", 404: "MODEL_NOT_FOUND", 429: "MODEL_RATE_LIMITED"}
        try:
            detail = response.json().get("error", {}).get("message")
        except (ValueError, AttributeError):
            detail = None
        raise ProviderError(detail or f"模型服务返回 HTTP {response.status_code}", codes.get(response.status_code, "MODEL_UPSTREAM_ERROR"))

    async def complete(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> CompletionResult:
        try:
            async with httpx.AsyncClient(timeout=self.provider.timeout_seconds) as client:
                response = await client.post(self.url, headers=self._headers(), json=self._payload(messages, temperature, max_tokens, False))
            self._raise(response)
            data = response.json()
            usage = data.get("usage") or {}
            return CompletionResult(
                content=data["choices"][0]["message"]["content"],
                input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
            )
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError("模型服务连接超时或不可用", "MODEL_UNAVAILABLE") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("模型服务返回了无法识别的响应") from exc

    async def stream(
        self, messages: list[dict[str, str]], temperature: float, max_tokens: int
    ) -> AsyncIterator[dict[str, object]]:
        try:
            async with httpx.AsyncClient(timeout=self.provider.timeout_seconds) as client:
                async with client.stream(
                    "POST", self.url, headers=self._headers(),
                    json=self._payload(messages, temperature, max_tokens, True),
                ) as response:
                    # ``client.stream`` does not preload the response body.
                    # Read error responses before parsing their JSON payload;
                    # otherwise httpx raises ResponseNotRead and breaks SSE.
                    if response.status_code >= 400:
                        await response.aread()
                    self._raise(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        usage = data.get("usage")
                        if usage:
                            yield {"type": "usage", "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}
                        choices = data.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta", {}).get("content")
                            if delta:
                                yield {"type": "delta", "content": delta}
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError("模型服务连接超时或不可用", "MODEL_UNAVAILABLE") from exc


def create_provider(provider: ModelProvider, model: AIModel) -> OpenAICompatibleProvider:
    if provider.adapter_type != "openai_compatible":
        raise ProviderError(f"不支持的平台适配器：{provider.adapter_type}", "PROVIDER_NOT_SUPPORTED")
    return OpenAICompatibleProvider(provider, model)

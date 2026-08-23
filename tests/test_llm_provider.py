import asyncio

import httpx
import pytest

from app.models import AIModel, ModelProvider
from app.services import llm_provider as provider_module
from app.services.llm_provider import OpenAICompatibleProvider, ProviderError


def test_stream_reads_upstream_error_before_parsing(monkeypatch) -> None:
    monkeypatch.setenv("TEST_PROVIDER_KEY", "secret")
    provider = ModelProvider(
        id="provider-id",
        name="Test Provider",
        base_url="https://provider.example/v1",
        api_key_env="TEST_PROVIDER_KEY",
        timeout_seconds=10,
    )
    model = AIModel(
        id="model-id",
        provider_id=provider.id,
        model_key="missing-model",
        name="Missing Model",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "invalid api key"}},
            request=request,
        )

    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        provider_module.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )

    async def consume_stream() -> None:
        instance = OpenAICompatibleProvider(provider, model)
        async for _ in instance.stream(
            [{"role": "user", "content": "hello"}], 0.2, 100
        ):
            pass

    with pytest.raises(ProviderError) as captured:
        asyncio.run(consume_stream())

    assert captured.value.code == "MODEL_AUTH_FAILED"
    assert str(captured.value) == "invalid api key"

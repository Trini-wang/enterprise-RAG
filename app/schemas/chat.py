from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelCreate(BaseModel):
    model_key: str = Field(min_length=1, max_length=150)
    name: str = Field(min_length=1, max_length=100)
    context_window: int = Field(default=32_000, ge=1024, le=10_000_000)
    supports_streaming: bool = True
    is_enabled: bool = True
    is_default: bool = False


class ModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    context_window: int | None = Field(default=None, ge=1024, le=10_000_000)
    supports_streaming: bool | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None


class ModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_key: str
    name: str
    context_window: int
    supports_streaming: bool
    is_enabled: bool
    is_default: bool


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    adapter_type: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = Field(min_length=8, max_length=500)
    api_key_env: str = Field(default="AI_API_KEY", min_length=1, max_length=100)
    api_key: str | None = Field(default=None, min_length=1, max_length=1000)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    is_enabled: bool = True


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    api_key_env: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(default=None, min_length=1, max_length=1000)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    is_enabled: bool | None = None


class ProviderAdminResponse(BaseModel):
    id: str
    name: str
    adapter_type: str
    base_url: str
    api_key_env: str
    has_api_key: bool
    timeout_seconds: int
    is_enabled: bool
    models: list[ModelResponse] = []


class ProviderPublicResponse(BaseModel):
    id: str
    name: str
    models: list[ModelResponse]


class ModelCatalogResponse(BaseModel):
    providers: list[ProviderPublicResponse]
    default_provider_id: str | None = None
    default_model_id: str | None = None


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str = Field(min_length=1, max_length=20_000)
    hit_template: str = Field(min_length=1, max_length=20_000)
    miss_template: str = Field(min_length=1, max_length=20_000)
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_output_tokens: int = Field(default=1500, ge=1, le=32_000)
    top_k: int = Field(default=3, ge=1, le=20)
    min_score: float = Field(default=0.15, ge=0, le=1)
    is_default: bool = False
    publish: bool = False

    @model_validator(mode="after")
    def templates_contain_question(self):
        if "{{question}}" not in self.hit_template or "{{question}}" not in self.miss_template:
            raise ValueError("命中和未命中模板都必须包含 {{question}}")
        if "{{context}}" not in self.hit_template:
            raise ValueError("知识命中模板必须包含 {{context}}")
        return self


class PromptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=20_000)
    hit_template: str | None = Field(default=None, min_length=1, max_length=20_000)
    miss_template: str | None = Field(default=None, min_length=1, max_length=20_000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=32_000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    min_score: float | None = Field(default=None, ge=0, le=1)
    is_default: bool | None = None


class PromptResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    is_default: bool
    version_id: str
    version: int
    system_prompt: str
    hit_template: str
    miss_template: str
    temperature: float
    max_output_tokens: int
    top_k: int
    min_score: float
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    provider_id: str | None = None
    model_id: str | None = None
    prompt_id: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    provider_id: str | None = None
    model_id: str | None = None
    prompt_id: str | None = None
    status: Literal["active", "archived"] | None = None


class CitationResponse(BaseModel):
    index: int
    document_id: str
    document_name: str
    chunk_id: str
    excerpt: str
    score: float


class KnowledgeResponse(BaseModel):
    searched: bool = True
    used: bool
    status: str = "completed"
    citations: list[CitationResponse]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    status: str
    knowledge: KnowledgeResponse | None = None
    provider: dict[str, str] | None = None
    model: dict[str, str] | None = None
    prompt_version_id: str | None = None
    usage: dict[str, int | None] | None = None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    provider_id: str | None
    model_id: str | None
    prompt_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=20_000)
    provider_id: str
    model_id: str
    prompt_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageResponse

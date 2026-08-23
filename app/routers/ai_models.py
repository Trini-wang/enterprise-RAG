from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_admin, get_current_user
from app.schemas import (
    ModelCatalogResponse, ModelCreate, ModelResponse, ModelUpdate,
    ProviderAdminResponse, ProviderCreate, ProviderUpdate,
)
from app.services.chat_store import chat_store

router = APIRouter()


@router.get("/ai/models", response_model=ModelCatalogResponse)
def model_catalog(_: dict[str, Any] = Depends(get_current_user)):
    return chat_store.public_catalog()


@router.get("/admin/model-providers", response_model=list[ProviderAdminResponse])
def providers(_: dict[str, Any] = Depends(get_current_admin)):
    return chat_store.admin_providers()


@router.post("/admin/model-providers", response_model=ProviderAdminResponse, status_code=status.HTTP_201_CREATED)
def create_provider(payload: ProviderCreate, _: dict[str, Any] = Depends(get_current_admin)):
    try:
        return chat_store.create_provider(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/admin/model-providers/{provider_id}", response_model=ProviderAdminResponse)
def update_provider(provider_id: str, payload: ProviderUpdate, _: dict[str, Any] = Depends(get_current_admin)):
    provider = chat_store.update_provider(provider_id, payload.model_dump(exclude_unset=True))
    if provider is None:
        raise HTTPException(status_code=404, detail="模型平台不存在")
    return provider


@router.post("/admin/model-providers/{provider_id}/models", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def create_model(provider_id: str, payload: ModelCreate, _: dict[str, Any] = Depends(get_current_admin)):
    try:
        return chat_store.create_model(provider_id, payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/admin/models/{model_id}", response_model=ModelResponse)
def update_model(model_id: str, payload: ModelUpdate, _: dict[str, Any] = Depends(get_current_admin)):
    model = chat_store.update_model(model_id, payload.model_dump(exclude_unset=True))
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    return model

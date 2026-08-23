from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_admin, get_current_user
from app.schemas import PromptCreate, PromptResponse, PromptUpdate
from app.services.chat_store import chat_store

router = APIRouter()


@router.get("", response_model=list[PromptResponse])
def list_prompts(user: dict[str, Any] = Depends(get_current_user)):
    return chat_store.list_prompts(include_drafts=user["role"] == "admin")


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: PromptCreate, admin: dict[str, Any] = Depends(get_current_admin)):
    return chat_store.create_prompt(admin["id"], payload.model_dump())


@router.patch("/{prompt_id}", response_model=PromptResponse)
def update_prompt(prompt_id: str, payload: PromptUpdate, admin: dict[str, Any] = Depends(get_current_admin)):
    result = chat_store.update_prompt(prompt_id, admin["id"], payload.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    return result


@router.post("/{prompt_id}/publish", response_model=PromptResponse)
def publish_prompt(prompt_id: str, _: dict[str, Any] = Depends(get_current_admin)):
    result = chat_store.publish_prompt(prompt_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    return result

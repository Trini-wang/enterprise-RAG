from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies.auth import get_current_user
from app.schemas import ConversationCreate, ConversationDetail, ConversationResponse, ConversationUpdate
from app.services.chat_store import chat_store

router = APIRouter()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, user: dict[str, Any] = Depends(get_current_user)):
    return chat_store.create_conversation(user["id"], payload.model_dump())


@router.get("", response_model=list[ConversationResponse])
def list_conversations(include_archived: bool = Query(False), user: dict[str, Any] = Depends(get_current_user)):
    return chat_store.list_conversations(user["id"], include_archived)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, user: dict[str, Any] = Depends(get_current_user)):
    conversation = chat_store.get_conversation(user["id"], conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {**ConversationResponse.model_validate(conversation).model_dump(), "messages": chat_store.messages(user["id"], conversation_id)}


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: str, payload: ConversationUpdate, user: dict[str, Any] = Depends(get_current_user)):
    result = chat_store.update_conversation(user["id"], conversation_id, payload.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, user: dict[str, Any] = Depends(get_current_user)) -> Response:
    if not chat_store.delete_conversation(user["id"], conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import get_current_admin, get_current_user
from app.schemas.user import AdminUserUpdate, UserResponse, UserUpdate
from app.services.user_store import user_store

router = APIRouter()


@router.get("", response_model=list[UserResponse])
def list_users(_: dict[str, Any] = Depends(get_current_admin)) -> list[dict[str, Any]]:
    return user_store.list_users()


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate, current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    updated = user_store.update_user(current_user["id"], payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return updated


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if current_user["role"] != "admin" and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="无权查看该用户")
    user = user_store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    current_admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    if user_id == current_admin["id"] and (
        changes.get("is_active") is False or changes.get("role") == "user"
    ):
        raise HTTPException(status_code=400, detail="不能禁用当前管理员或降低自己的权限")
    updated = user_store.update_user(user_id, changes)
    if updated is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, current_admin: dict[str, Any] = Depends(get_current_admin)) -> Response:
    if user_id == current_admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除当前管理员")
    if not user_store.delete_user(user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

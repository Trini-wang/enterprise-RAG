import os
import re
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.dependencies.auth import get_current_user

router = APIRouter()
UPLOAD_ROOT = Path(os.getenv("RAG_UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads"))).resolve()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
STORED_NAME_RE = re.compile(r"^[0-9a-f]{32}_.+")


class FileInfo(BaseModel):
    filename: str
    original_filename: str
    size: int
    content_type: str | None = None
    download_url: str


def _user_directory(user_id: str) -> Path:
    directory = UPLOAD_ROOT / user_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_owned_file(user_id: str, filename: str) -> Path:
    directory = _user_directory(user_id).resolve()
    if not STORED_NAME_RE.fullmatch(filename) or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return path


def _file_info(path: Path) -> FileInfo:
    original = path.name.split("_", 1)[1]
    return FileInfo(filename=path.name, original_filename=original, size=path.stat().st_size,
                    download_url=f"/files/{path.name}")


@router.post("/upload", response_model=FileInfo, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), user: dict[str, Any] = Depends(get_current_user)) -> FileInfo:
    original_name = Path(file.filename or "upload.bin").name
    safe_name = re.sub(r"[^\w.()\-\u4e00-\u9fff]+", "_", original_name).strip("._")
    safe_name = safe_name[:180] or "upload.bin"
    filename = f"{uuid.uuid4().hex}_{safe_name}"
    destination = _user_directory(user["id"]) / filename
    size = 0
    try:
        async with aiofiles.open(destination, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"文件不能超过 {MAX_UPLOAD_BYTES} 字节")
                await output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="文件保存失败") from exc
    finally:
        await file.close()
    return FileInfo(filename=filename, original_filename=original_name, size=size,
                    content_type=file.content_type, download_url=f"/files/{filename}")


@router.get("", response_model=list[FileInfo])
def list_files(user: dict[str, Any] = Depends(get_current_user)) -> list[FileInfo]:
    paths = sorted(_user_directory(user["id"]).iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
    return [_file_info(path) for path in paths if path.is_file() and STORED_NAME_RE.fullmatch(path.name)]


@router.get("/{filename}")
def download_file(filename: str, user: dict[str, Any] = Depends(get_current_user)) -> FileResponse:
    path = _resolve_owned_file(user["id"], filename)
    return FileResponse(path, filename=path.name.split("_", 1)[1])


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(filename: str, user: dict[str, Any] = Depends(get_current_user)) -> None:
    _resolve_owned_file(user["id"], filename).unlink()

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import ai_models, auth, chat, conversations, docs, files, prompts, query, users

app = FastAPI(
    title="企业文档RAG系统",
    description="简单的文档上传、检索与问答示例接口",
    version="0.1.0",
)

app.include_router(docs, prefix="/docs", tags=["documents"])
app.include_router(query, prefix="/query", tags=["query"])
app.include_router(auth, prefix="/auth", tags=["auth"])
app.include_router(users, prefix="/users", tags=["users"])
app.include_router(files, prefix="/files", tags=["files"])
app.include_router(ai_models, tags=["ai-models"])
app.include_router(chat, prefix="/chat", tags=["chat"])
app.include_router(conversations, prefix="/conversations", tags=["conversations"])
app.include_router(prompts, prefix="/prompts", tags=["prompts"])

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """Serve the browser client from the same origin as the API."""
    return FileResponse(STATIC_DIR / "index.html")

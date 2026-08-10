from fastapi import FastAPI

from app.routers import docs, query

app = FastAPI(
    title="企业文档RAG系统",
    description="简单的文档上传、检索与问答示例接口",
    version="0.1.0",
)

app.include_router(docs, prefix="/docs", tags=["documents"])
app.include_router(query, prefix="/query", tags=["query"])


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "企业文档RAG系统已启动，请访问 /docs/list 或 /query/search"}

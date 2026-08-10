from typing import List

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    name: str = Field(..., description="文档名称")
    content: str = Field(..., description="文档内容")


class DocumentResponse(BaseModel):
    doc_id: str
    name: str
    chunk_count: int


class DocumentSummary(BaseModel):
    doc_id: str
    name: str
    chunk_count: int


class QueryRequest(BaseModel):
    query: str = Field(..., description="用户查询文本")
    top_k: int = Field(3, description="返回多少条最相关文档片段")


class QueryResult(BaseModel):
    text: str
    source: str
    score: float


class QueryResponse(BaseModel):
    query: str
    results: List[QueryResult]
    answer: str

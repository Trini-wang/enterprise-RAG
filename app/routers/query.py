from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.schemas import QueryRequest, QueryResponse, QueryResult
from app.services.document_store import store

router = APIRouter()


@router.post("/search", response_model=QueryResponse)
def query_documents(payload: QueryRequest, _: dict[str, Any] = Depends(get_current_user)) -> QueryResponse:
    matches = store.search(payload.query, payload.top_k)
    results = [QueryResult(text=item["text"], source=item["source"], score=item["score"]) for item in matches]
    answer = store.answer_question(payload.query, payload.top_k)
    return QueryResponse(query=payload.query, results=results, answer=answer)

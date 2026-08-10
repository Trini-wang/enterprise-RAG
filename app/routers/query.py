from fastapi import APIRouter

from app.schemas import QueryRequest, QueryResponse, QueryResult
from app.services.document_store import store

router = APIRouter()


@router.post("/search", response_model=QueryResponse)
def query_documents(payload: QueryRequest) -> QueryResponse:
    matches = store.search(payload.query, payload.top_k)
    results = [QueryResult(text=item["text"], source=item["source"], score=item["score"]) for item in matches]
    answer = store.answer_question(payload.query, payload.top_k)
    return QueryResponse(query=payload.query, results=results, answer=answer)

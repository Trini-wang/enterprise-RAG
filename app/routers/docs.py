from fastapi import APIRouter, HTTPException

from app.schemas import DocumentCreate, DocumentResponse, DocumentSummary
from app.services.document_store import store

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse)
def upload_document(payload: DocumentCreate) -> DocumentResponse:
    try:
        saved = store.add_document(payload.name, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return DocumentResponse(
        doc_id=saved["doc_id"],
        name=saved["name"],
        chunk_count=saved["chunk_count"],
    )


@router.get("/list", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    return [DocumentSummary(**doc) for doc in store.list_documents()]


@router.get("/{doc_id}")
def get_document(doc_id: str) -> dict[str, object]:
    doc = store.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="未找到文档")
    return {
        "doc_id": doc_id,
        "name": doc["name"],
        "content": doc["content"],
        "chunk_count": doc["chunk_count"],
    }

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user
from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.chat_store import chat_store
from app.services.document_store import store as document_store
from app.services.llm_provider import ProviderError, create_provider

router = APIRouter()
chat_service = ChatService(chat_store, document_store)


def sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/completions", response_model=ChatResponse)
async def completion(payload: ChatRequest, user: dict[str, Any] = Depends(get_current_user)):
    try:
        turn = chat_service.prepare(user["id"], payload.model_dump())
        message = await chat_service.complete(turn)
        return {"conversation_id": turn.conversation_id, "message": message}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail={"code": exc.code, "message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/completions/stream")
async def stream_completion(payload: ChatRequest, user: dict[str, Any] = Depends(get_current_user)):
    try:
        turn = chat_service.prepare(user["id"], payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def events():
        started = time.perf_counter()
        content, usage = [], {"input_tokens": None, "output_tokens": None}
        public_citations = [{
            "index": item["citation_index"], "document_id": item["document_id"],
            "document_name": item["document_name"], "chunk_id": item["chunk_id"],
            "excerpt": item["excerpt"], "score": item["score"],
        } for item in turn.citations]
        yield sse("message.created", {"conversation_id": turn.conversation_id})
        yield sse("retrieval.completed", {
            "status": turn.retrieval_status, "used": bool(turn.citations), "citations": public_citations,
        })
        try:
            provider = create_provider(turn.provider, turn.model)
            async for item in provider.stream(turn.messages, turn.prompt["temperature"], turn.prompt["max_output_tokens"]):
                if item["type"] == "delta":
                    content.append(str(item["content"]))
                    yield sse("message.delta", {"content": item["content"]})
                elif item["type"] == "usage":
                        usage = {"input_tokens": item.get("input_tokens"), "output_tokens": item.get("output_tokens")}
            full_content = "".join(content)
            title = await chat_service.generate_title(turn, full_content, provider)
            message = chat_store.save_assistant_message(
                turn.conversation_id, full_content, turn.provider, turn.model, turn.prompt,
                turn.retrieval_status, turn.citations, usage, round((time.perf_counter() - started) * 1000),
                title,
            )
            yield sse("message.completed", {"message": message})
        except ProviderError as exc:
            yield sse("message.failed", {"code": exc.code, "message": str(exc), "retryable": True})
        except asyncio.CancelledError:
            raise

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

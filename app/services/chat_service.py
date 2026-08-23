import time
import re
from dataclasses import dataclass
from typing import Any

from app.services.chat_store import ChatStore
from app.services.document_store import DocumentStore
from app.services.llm_provider import CompletionResult, create_provider


@dataclass
class PreparedTurn:
    conversation_id: str
    provider: Any
    model: Any
    prompt: dict[str, Any]
    messages: list[dict[str, str]]
    citations: list[dict[str, Any]]
    retrieval_status: str
    question: str
    needs_title: bool


class ChatService:
    def __init__(self, chat_store: ChatStore, document_store: DocumentStore) -> None:
        self.store = chat_store
        self.documents = document_store

    def prepare(self, user_id: str, payload: dict[str, Any]) -> PreparedTurn:
        provider, model = self.store.resolve_model(payload["provider_id"], payload["model_id"])
        prompt = self.store.get_prompt(payload.get("prompt_id"))
        conversation_id = payload.get("conversation_id")
        if conversation_id:
            conversation = self.store.get_conversation(user_id, conversation_id)
            if conversation is None:
                raise LookupError("会话不存在")
        else:
            conversation = self.store.create_conversation(user_id, {
                "provider_id": provider.id, "model_id": model.id, "prompt_id": prompt["id"]
            })
        history = self.store.history(user_id, conversation.id, limit=20)
        self.store.add_user_message(conversation.id, payload["message"])

        retrieval_status = "completed"
        try:
            results = self.documents.search(payload["message"], prompt["top_k"])
        except Exception:
            results, retrieval_status = [], "failed"
        valid = [item for item in results if float(item["score"]) >= prompt["min_score"]]
        citations = [{
            "citation_index": index, "document_id": str(item["document_id"]),
            "document_name": str(item["source"]), "chunk_id": str(item["chunk_id"]),
            "excerpt": str(item["text"]), "score": float(item["score"]),
        } for index, item in enumerate(valid, 1)]
        if citations:
            context = "\n\n".join(
                f"[{item['citation_index']}] 来源：{item['document_name']}\n{item['excerpt']}" for item in citations
            )
            rendered = prompt["hit_template"].replace("{{context}}", context)
        else:
            rendered = prompt["miss_template"]
        rendered = rendered.replace("{{question}}", payload["message"]).replace("{{history}}", "")
        rendered = rendered.replace("{{citations}}", ", ".join(f"[{item['citation_index']}]" for item in citations))
        messages = [{"role": "system", "content": prompt["system_prompt"]}, *history, {"role": "user", "content": rendered}]
        return PreparedTurn(
            conversation.id, provider, model, prompt, messages, citations, retrieval_status,
            payload["message"], conversation.title == "新对话",
        )

    @staticmethod
    def fallback_title(question: str) -> str:
        title = re.sub(r"\s+", " ", question).strip(" \"'“”‘’。！？!?，,")
        return title[:28] or "新对话"

    async def generate_title(self, turn: PreparedTurn, answer: str, provider_instance=None) -> str:
        if not turn.needs_title:
            return ""
        instance = provider_instance or create_provider(turn.provider, turn.model)
        messages = [
            {
                "role": "system",
                "content": "请为这段对话生成一个4到12个汉字的简洁标题。只输出标题，不要引号、句号、解释或前缀。",
            },
            {
                "role": "user",
                "content": f"用户问题：{turn.question}\n助手回答：{answer[:1000]}",
            },
        ]
        try:
            result = await instance.complete(messages, 0.2, 30)
            title = re.sub(r"\s+", " ", result.content).strip(" \"'“”‘’。！？!?，,")
            if title:
                return title[:28]
        except Exception:
            pass
        return self.fallback_title(turn.question)

    async def complete(self, turn: PreparedTurn) -> dict[str, Any]:
        started = time.perf_counter()
        provider_instance = create_provider(turn.provider, turn.model)
        result: CompletionResult = await provider_instance.complete(
            turn.messages, turn.prompt["temperature"], turn.prompt["max_output_tokens"]
        )
        title = await self.generate_title(turn, result.content, provider_instance)
        return self.store.save_assistant_message(
            turn.conversation_id, result.content, turn.provider, turn.model, turn.prompt,
            turn.retrieval_status, turn.citations,
            {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
            round((time.perf_counter() - started) * 1000), title,
        )

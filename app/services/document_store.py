import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

WORD_RE = re.compile(r"\w+", flags=re.U)


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    name: str
    text: str
    tfidf: Dict[str, float]
    vector_length: float


class DocumentStore:
    def __init__(self) -> None:
        self.documents: Dict[str, Dict[str, object]] = {}
        self.chunks: List[DocumentChunk] = []
        self.df: Counter = Counter()
        self.idf: Dict[str, float] = {}
        self.total_chunks: int = 0

    @staticmethod
    def _normalize(text: str) -> List[str]:
        return [token.lower() for token in WORD_RE.findall(text)]

    @staticmethod
    def _split_chunk(text: str, max_chars: int = 800) -> List[str]:
        if len(text) <= max_chars:
            return [text.strip()]

        parts: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                boundary = text.rfind("。", start, end)
                if boundary > start:
                    end = boundary + 1
            part = text[start:end].strip()
            if part:
                parts.append(part)
            start = end
        return parts

    @staticmethod
    def _normalize_tf(tokens: List[str]) -> Dict[str, float]:
        frequencies = Counter(tokens)
        length = math.sqrt(sum(count * count for count in frequencies.values()))
        if not length:
            return {}
        return {token: count / length for token, count in frequencies.items()}

    def _recompute_idf(self) -> None:
        if self.total_chunks == 0:
            self.idf = {}
            return
        self.idf = {
            token: math.log((self.total_chunks + 1) / (self.df[token] + 1)) + 1.0
            for token in self.df
        }

    def _build_tfidf(self, tokens: List[str]) -> Dict[str, float]:
        tf = self._normalize_tf(tokens)
        if not tf:
            return {}
        tfidf = {token: value * self.idf.get(token, 1.0) for token, value in tf.items()}
        length = math.sqrt(sum(value * value for value in tfidf.values()))
        if not length:
            return tfidf
        return {token: value / length for token, value in tfidf.items()}

    def add_document(self, name: str, content: str) -> Dict[str, object]:
        text = content.strip()
        if not text:
            raise ValueError("文档内容不能为空")

        doc_id = str(uuid.uuid4())
        chunk_texts: List[str] = []
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
        if not paragraphs:
            paragraphs = [text]

        for paragraph in paragraphs:
            for chunk_text in self._split_chunk(paragraph):
                chunk_texts.append(chunk_text)

        if not chunk_texts:
            chunk_texts = [text]

        chunk_ids: List[str] = []
        for chunk_text in chunk_texts:
            chunk_id = str(uuid.uuid4())
            tokens = self._normalize(chunk_text)
            self.total_chunks += 1
            for token in set(tokens):
                self.df[token] += 1
            self._recompute_idf()
            tfidf = self._build_tfidf(tokens)
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                name=name,
                text=chunk_text,
                tfidf=tfidf,
                vector_length=math.sqrt(sum(score * score for score in tfidf.values())),
            )
            self.chunks.append(chunk)
            chunk_ids.append(chunk_id)

        self.documents[doc_id] = {
            "name": name,
            "content": content,
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunk_ids),
        }

        return {
            "doc_id": doc_id,
            "name": name,
            "chunk_count": len(chunk_ids),
        }

    def _rank_chunks(self, query: str, top_k: int) -> List[DocumentChunk]:
        tokens = self._normalize(query)
        if not tokens:
            return []

        query_vector = self._build_tfidf(tokens)
        if not query_vector:
            return []

        scores: List[tuple[float, DocumentChunk]] = []
        for chunk in self.chunks:
            score = sum(query_vector.get(token, 0.0) * chunk.tfidf.get(token, 0.0) for token in query_vector)
            if score > 0:
                scores.append((score, chunk))

        scores.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scores[:top_k]]

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, object]]:
        matches = self._rank_chunks(query, top_k)
        return [
            {
                "text": chunk.text,
                "source": chunk.name,
                "score": float(round(sum(query_word in chunk.text for query_word in query.split()) / max(1, len(query.split())), 4)),
            }
            for chunk in matches
        ]

    def answer_question(self, query: str, top_k: int = 3) -> str:
        results = self._rank_chunks(query, top_k)
        if not results:
            return "没有找到相关的文档内容。"

        pieces = [f"来源：{chunk.name}\n{chunk.text}" for chunk in results]
        return (
            "已检索到最相关的内容，供回答参考：\n\n"
            + "\n\n".join(pieces)
            + "\n\n请根据以上内容补充你的问题。"
        )

    def list_documents(self) -> List[Dict[str, object]]:
        return [
            {
                "doc_id": doc_id,
                "name": info["name"],
                "chunk_count": info["chunk_count"],
            }
            for doc_id, info in self.documents.items()
        ]

    def get_document(self, doc_id: str) -> Optional[Dict[str, object]]:
        return self.documents.get(doc_id)


store = DocumentStore()

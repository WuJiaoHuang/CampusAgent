"""Chroma persistence, synchronization and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from campus_agent.rag.documents import DocumentChunk
from campus_agent.rag.embeddings import EmbeddingBackend


@dataclass(frozen=True)
class SearchResult:
    text: str
    distance: float
    source_path: str
    heading_path: str
    source_refs: tuple[str, ...]


class KnowledgeStore:
    def __init__(
        self,
        db_path: Path,
        embedder: EmbeddingBackend,
        collection_name: str = "campusagent_knowledge",
    ) -> None:
        self._client = chromadb.PersistentClient(path=str(db_path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = embedder

    def sync(self, chunks: list[DocumentChunk], batch_size: int = 16) -> int:
        desired = {chunk.chunk_id for chunk in chunks}
        existing = self._collection.get(include=[])["ids"]
        stale = sorted(set(existing) - desired)
        if stale:
            self._collection.delete(ids=stale)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            self._collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                metadatas=[chunk.metadata() for chunk in batch],
                embeddings=self._embedder.embed([chunk.text for chunk in batch]),
            )
        return len(chunks)

    def count(self) -> int:
        return self._collection.count()

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        embedding = self._embedder.embed([query])[0]
        result: dict[str, Any] = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        return [
            SearchResult(
                text=document,
                distance=float(distance),
                source_path=metadata.get("source_path", ""),
                heading_path=metadata.get("heading_path", ""),
                source_refs=tuple(filter(None, metadata.get("source_refs", "").splitlines())),
            )
            for document, distance, metadata in zip(documents, distances, metadatas, strict=True)
        ]

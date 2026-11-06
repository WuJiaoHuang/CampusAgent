"""Embedding backends for local and test use."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class EmbeddingBackend(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class BgeEmbedding:
    """CPU SentenceTransformers wrapper; model download failures are explicit."""

    def __init__(self, model_name: str, cache_dir: Path, batch_size: int = 16) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError("缺少 sentence-transformers，请先执行 uv sync") from error
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._batch_size = batch_size
        try:
            self._model = SentenceTransformer(
                model_name,
                cache_folder=str(cache_dir),
                device="cpu",
            )
        except Exception as error:
            raise RuntimeError(
                f"无法下载或加载本地 Embedding 模型 {model_name}；未切换到付费服务"
            ) from error

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.tolist()

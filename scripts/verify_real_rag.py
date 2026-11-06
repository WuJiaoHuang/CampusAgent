"""Download/load BGE once and verify three Chinese retrieval questions."""

from __future__ import annotations

import tempfile
from pathlib import Path

from campus_agent.config import Settings
from campus_agent.rag.documents import load_markdown_chunks
from campus_agent.rag.embeddings import BgeEmbedding
from campus_agent.rag.store import KnowledgeStore

CASES = (
    ("培训名额已满还能报名吗？", ("容量", "名额", "报名")),
    ("取消报名以后可以重新报名吗？", ("重新报名", "取消", "状态")),
    ("视频学习到多少比例算完成？", ("完成", "视频", "进度")),
)


def main() -> None:
    settings = Settings()
    embedder = BgeEmbedding(
        settings.embedding_model,
        settings.model_cache_dir,
        settings.embedding_batch_size,
    )
    with tempfile.TemporaryDirectory(
        prefix="campusagent-rag-", ignore_cleanup_errors=True
    ) as temporary_dir:
        store = KnowledgeStore(Path(temporary_dir) / "chroma", embedder)
        chunks = load_markdown_chunks(settings.knowledge_dir)
        store.sync(chunks, settings.embedding_batch_size)
        assert store.count() == len(chunks) > 0
        for question, keywords in CASES:
            results = store.search(question, top_k=5)
            assert results, question
            matching = [
                result
                for result in results
                if any(keyword in result.text for keyword in keywords) and result.source_refs
            ]
            assert matching, f"未检索到带 Source 引用的相关片段：{question}"
            best = matching[0]
            print(f"PASS: {question} -> {best.source_path} / {best.heading_path}")
            print(f"  distance={best.distance:.4f}; refs={len(best.source_refs)}")


if __name__ == "__main__":
    main()

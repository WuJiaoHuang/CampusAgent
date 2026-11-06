"""Command line entry point for building and querying the local knowledge base."""

from __future__ import annotations

import argparse

from campus_agent.config import Settings
from campus_agent.rag.documents import load_markdown_chunks
from campus_agent.rag.embeddings import BgeEmbedding
from campus_agent.rag.store import KnowledgeStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="campus-agent-rag")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="同步 Markdown 知识库到 Chroma")
    build.add_argument("--knowledge-dir", default=None)
    query = subparsers.add_parser("query", help="查询本地知识库")
    query.add_argument("question")
    query.add_argument("-k", "--top-k", type=int, default=5)
    args = parser.parse_args()

    settings = Settings()
    knowledge_dir = (
        settings.knowledge_dir
        if args.command == "query" or args.knowledge_dir is None
        else args.knowledge_dir
    )
    embedder = BgeEmbedding(
        settings.embedding_model,
        settings.model_cache_dir,
        settings.embedding_batch_size,
    )
    store = KnowledgeStore(settings.vector_db_path, embedder)
    if args.command == "build":
        chunks = load_markdown_chunks(knowledge_dir)
        synced = store.sync(chunks, settings.embedding_batch_size)
        print(f"已同步 {synced} 个分块，当前索引 {store.count()} 个")
        return
    for index, result in enumerate(store.search(args.question, args.top_k), start=1):
        print(
            f"[{index}] distance={result.distance:.4f} "
            f"source={result.source_path} heading={result.heading_path}"
        )
        print("Source refs:", " | ".join(result.source_refs))
        print(result.text)
        print()


if __name__ == "__main__":
    main()

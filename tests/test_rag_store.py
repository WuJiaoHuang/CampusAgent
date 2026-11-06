from pathlib import Path

from campus_agent.rag.documents import load_markdown_chunks
from campus_agent.rag.store import KnowledgeStore


class FakeEmbedding:
    def embed(self, texts):
        return [[
            float("enrollment" in text or "报名" in text),
            float("学习" in text or "进度" in text),
            float("课程" in text or "目录" in text),
        ] for text in texts]


def write_doc(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def test_markdown_loader_preserves_headings_and_sources(tmp_path):
    write_doc(
        tmp_path,
        "faq.md",
        (
            "# FAQ\n\n## 报名\n\n### 如何报名？\n\n调用报名接口。\n\n"
            "Source: `CampusTrain/x.java#Demo.method`\n"
        ),
    )

    chunks = load_markdown_chunks(tmp_path)

    assert len(chunks) == 3
    leaf = chunks[-1]
    assert leaf.heading_path == "FAQ > 报名 > 如何报名？"
    assert "调用报名接口" in leaf.text
    assert leaf.source_refs == ("CampusTrain/x.java#Demo.method",)


def test_sync_repeat_update_delete_and_persist(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    write_doc(knowledge, "one.md", "# 课程\n\n## 课程详情\n\n课程目录和详情。\n")
    write_doc(knowledge, "two.md", "# 报名\n\n## 报名条件\n\n报名需要有效身份。\n")
    db_path = tmp_path / "chroma"

    store = KnowledgeStore(db_path, FakeEmbedding())
    chunks = load_markdown_chunks(knowledge)
    assert store.sync(chunks, batch_size=1) == 4
    assert store.count() == 4
    assert store.sync(chunks, batch_size=2) == 4
    assert store.count() == 4

    write_doc(knowledge, "two.md", "# 报名\n\n## 报名条件\n\n学习进度需要有效报名。\n")
    write_doc(knowledge, "three.md", "# 学习\n\n## 进度\n\n学习进度可以查询。\n")
    updated = load_markdown_chunks(knowledge)
    store.sync(updated)
    assert store.count() == 6
    assert store.search("学习进度", top_k=2)[0].source_path in {"two.md", "three.md"}

    (knowledge / "two.md").unlink()
    store.sync(load_markdown_chunks(knowledge))
    assert store.count() == 4

    restarted = KnowledgeStore(db_path, FakeEmbedding())
    assert restarted.count() == 4
    assert restarted.search("课程目录", top_k=1)[0].source_path == "one.md"

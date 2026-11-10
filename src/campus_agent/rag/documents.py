"""Markdown loading and deterministic heading-based chunking."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source_path: str
    heading_path: str
    source_refs: tuple[str, ...]

    def metadata(self) -> dict[str, str]:
        return {
            "source_path": self.source_path,
            "heading_path": self.heading_path,
            "source_refs": "\n".join(self.source_refs),
        }


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_SOURCE_RE = re.compile(r"^Source:\s*`([^`]+)`\s*$")


def load_markdown_chunks(knowledge_dir: Path) -> list[DocumentChunk]:
    """Load every Markdown file and split content at heading boundaries."""
    chunks: list[DocumentChunk] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        chunks.extend(_parse_file(path, knowledge_dir))
    return chunks


def _parse_file(path: Path, knowledge_dir: Path) -> list[DocumentChunk]:
    relative_path = path.relative_to(knowledge_dir).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    # 当前标题层级
    heading_stack: list[str] = []
    # 当前chunk的文本内容
    current_lines: list[str] = []
    current_headings: tuple[str, ...] = ()
    chunks: list[DocumentChunk] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body or not current_headings:
            return
        heading_path = " > ".join(current_headings)
        text = f"标题：{heading_path}\n\n{body}"
        refs = tuple(
            match.group(1)
            for line in current_lines
            if (match := _SOURCE_RE.match(line))
        )
        digest = hashlib.sha256(f"{relative_path}\0{heading_path}\0{text}".encode()).hexdigest()
        chunks.append(DocumentChunk(digest, text, relative_path, heading_path, refs))

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(match.group(2))
            current_headings = tuple(heading_stack)
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()
    return chunks

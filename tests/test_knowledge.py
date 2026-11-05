import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMPUS_TRAIN_ROOT = Path(r"D:\HuaweiMoveData\Users\HW\Desktop\CampusTrain")
KNOWLEDGE_FILES = (
    "faq.md",
    "enrollment_rules.md",
    "cancellation_rules.md",
    "learning_rules.md",
)
REQUIRED_HEADINGS = ("# ", "## ", "### ")


def test_knowledge_files_have_chunkable_markdown_structure():
    for name in KNOWLEDGE_FILES:
        path = PROJECT_ROOT / "knowledge" / name
        assert path.is_file(), name
        content = path.read_text(encoding="utf-8")
        assert all(heading in content for heading in REQUIRED_HEADINGS), name
        assert "Source: `CampusTrain/" in content, name
        assert not re.search(r"^#{4,}\s", content, flags=re.MULTILINE), name


def test_knowledge_source_references_resolve_to_existing_code_symbols():
    references = []
    for path in (PROJECT_ROOT / "knowledge").glob("*.md"):
        content = path.read_text(encoding="utf-8")
        references.extend(re.findall(r"Source: `([^`]+)`", content))

    assert references
    for reference in references:
        relative_path, symbol = reference.split("#", 1)
        source_path = CAMPUS_TRAIN_ROOT / Path(relative_path).relative_to("CampusTrain")
        assert source_path.is_file(), reference
        source = source_path.read_text(encoding="utf-8")
        symbol_name = symbol.rsplit(".", 1)[-1]
        assert symbol_name in source, reference

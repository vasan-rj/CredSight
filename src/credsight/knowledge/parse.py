"""Docling parse stage (ref-doc 05). Turns source documents into clean Markdown — the
GBrain source of truth.

Markdown is parsed directly (Docling's own output format is Markdown, so seeded .md docs
need no conversion). PDFs/DOCX go through Docling when the optional `knowledge` extra is
installed; otherwise a clear error tells you to install it or seed Markdown. This keeps the
heavy Docling/torch stack optional while the brain runs on Markdown today."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import cocoindex as _coco
    _memo = _coco.fn(memo=True)
except ImportError:
    _memo = lambda f: f  # no-op when cocoindex not installed


@dataclass(frozen=True)
class ParsedDoc:
    path: str
    title: str
    markdown: str


def _title_of(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def parse_document(path: Path) -> ParsedDoc:
    """Parse one source document into Markdown."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        text = path.read_text(encoding="utf-8")
        return ParsedDoc(str(path), _title_of(text, path.stem), text)
    if suffix in {".pdf", ".docx"}:
        return _parse_with_docling(path)
    raise ValueError(f"Unsupported document type for the knowledge brain: {path.name}")


@_memo
def _docling_to_markdown(path_str: str) -> str:
    """PDF/DOCX → Markdown via Docling. Memoized by CocoIndex — unchanged files skip
    re-conversion across runs (Docling is expensive; seconds to minutes per PDF)."""
    from docling.document_converter import DocumentConverter
    return DocumentConverter().convert(path_str).document.export_to_markdown()


def _parse_with_docling(path: Path) -> ParsedDoc:
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401 — availability check
    except ModuleNotFoundError as e:
        raise RuntimeError(
            f"Parsing {path.name} needs Docling: `pip install -e \".[knowledge]\"`. "
            f"Until then, seed policy as Markdown under knowledge/policies/."
        ) from e
    markdown = _docling_to_markdown(str(path))
    return ParsedDoc(str(path), _title_of(markdown, path.stem), markdown)

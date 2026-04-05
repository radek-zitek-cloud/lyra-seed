"""Markdown document chunker — splits by headings."""

import re
from pathlib import Path

from pydantic import BaseModel

# ~8K tokens ≈ ~32K chars is a safe limit for embedding APIs.
DEFAULT_MAX_CHUNK_CHARS = 30_000


class DocumentChunk(BaseModel):
    """A chunk of a document with metadata."""

    content: str
    source: str  # filename
    heading_path: str  # e.g., "Memory System > Context Memory"
    directory: str = ""  # parent directory path


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _split_large_chunk(
    content: str,
    source: str,
    heading_path: str,
    max_chars: int,
) -> list[DocumentChunk]:
    """Split an oversized chunk on paragraph boundaries."""
    if len(content) <= max_chars:
        return [
            DocumentChunk(
                content=content,
                source=source,
                heading_path=heading_path,
            )
        ]

    chunks: list[DocumentChunk] = []
    paragraphs = re.split(r"\n\n+", content)
    current = ""
    part = 1

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(
                DocumentChunk(
                    content=current.strip(),
                    source=source,
                    heading_path=f"{heading_path} [{part}]",
                )
            )
            part += 1
            current = ""
        current += ("\n\n" if current else "") + para

    if current.strip():
        label = (
            f"{heading_path} [{part}]" if part > 1 else heading_path
        )
        chunks.append(
            DocumentChunk(
                content=current.strip(),
                source=source,
                heading_path=label,
            )
        )

    return chunks


def chunk_markdown(
    path: Path,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[DocumentChunk]:
    """Split a markdown file into chunks by headings.

    Each heading starts a new chunk. Nested headings create
    hierarchical heading paths (e.g., "Parent > Child").
    Chunks exceeding max_chunk_chars are further split on
    paragraph boundaries.
    """
    text = path.read_text(encoding="utf-8")
    source = path.name

    # Find all heading positions
    headings: list[tuple[int, int, str]] = []  # (pos, level, title)
    for m in _HEADING_RE.finditer(text):
        level = len(m.group(1))
        title = m.group(2).strip()
        headings.append((m.start(), level, title))

    if not headings:
        # No headings — return the whole document, split if needed
        content = text.strip()
        if content:
            return _split_large_chunk(
                content, source, path.stem, max_chunk_chars
            )
        return []

    chunks: list[DocumentChunk] = []

    # Content before first heading (if any)
    intro = text[: headings[0][0]].strip()
    if intro:
        chunks.extend(
            _split_large_chunk(
                intro, source, path.stem, max_chunk_chars
            )
        )

    # Build heading path stack
    path_stack: list[tuple[int, str]] = []  # (level, title)

    for i, (pos, level, title) in enumerate(headings):
        # Get content between this heading and the next
        if i + 1 < len(headings):
            end = headings[i + 1][0]
        else:
            end = len(text)

        content = text[pos:end].strip()
        # Remove the heading line from content
        first_newline = content.find("\n")
        if first_newline > 0:
            body = content[first_newline:].strip()
        else:
            body = ""

        # Update heading path stack
        while path_stack and path_stack[-1][0] >= level:
            path_stack.pop()
        path_stack.append((level, title))

        heading_path = " > ".join(t for _, t in path_stack)

        # Include both heading and body as content
        if body:
            chunks.extend(
                _split_large_chunk(
                    body, source, heading_path, max_chunk_chars
                )
            )

    return chunks

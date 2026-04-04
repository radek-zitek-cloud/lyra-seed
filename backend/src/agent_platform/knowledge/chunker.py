"""Markdown document chunker — splits by headings."""

import re
from pathlib import Path

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    """A chunk of a document with metadata."""

    content: str
    source: str  # filename
    heading_path: str  # e.g., "Memory System > Context Memory"


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def chunk_markdown(path: Path) -> list[DocumentChunk]:
    """Split a markdown file into chunks by headings.

    Each heading starts a new chunk. Nested headings create
    hierarchical heading paths (e.g., "Parent > Child").
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
        # No headings — return the whole document as one chunk
        content = text.strip()
        if content:
            return [
                DocumentChunk(
                    content=content,
                    source=source,
                    heading_path=path.stem,
                )
            ]
        return []

    chunks: list[DocumentChunk] = []

    # Content before first heading (if any)
    intro = text[: headings[0][0]].strip()
    if intro:
        chunks.append(
            DocumentChunk(
                content=intro,
                source=source,
                heading_path=path.stem,
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
            chunks.append(
                DocumentChunk(
                    content=body,
                    source=source,
                    heading_path=heading_path,
                )
            )

    return chunks

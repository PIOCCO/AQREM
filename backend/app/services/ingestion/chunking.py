from dataclasses import dataclass


@dataclass
class TextChunk:
    content: str
    line_start: int | None
    line_end: int | None
    chunk_index: int


def chunk_text(content: str, max_chars: int = 1200, overlap: int = 150) -> list[TextChunk]:
    if not content.strip():
        return []
    lines = content.splitlines(keepends=True)
    chunks: list[TextChunk] = []
    buffer = ""
    line_start = 1
    current_line = 1
    chunk_index = 0

    def flush(end_line: int) -> None:
        nonlocal buffer, line_start, chunk_index
        if buffer.strip():
            chunks.append(
                TextChunk(
                    content=buffer.strip(),
                    line_start=line_start,
                    line_end=end_line,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1
        buffer = ""
        line_start = end_line + 1

    for line in lines:
        if len(buffer) + len(line) > max_chars and buffer:
            flush(current_line - 1)
            if overlap > 0 and chunks:
                tail = chunks[-1].content[-overlap:]
                buffer = tail + line
                line_start = max(1, current_line - tail.count("\n"))
            else:
                buffer = line
                line_start = current_line
        else:
            if not buffer:
                line_start = current_line
            buffer += line
        current_line += 1

    if buffer.strip():
        flush(current_line - 1)
    return chunks

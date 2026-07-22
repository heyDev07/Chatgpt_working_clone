DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(
    text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """Recursive-style chunking: split on paragraph boundaries first, greedily packing
    paragraphs up to chunk_size; a single paragraph longer than chunk_size falls back to a
    sliding character window. Overlap is then stitched between consecutive chunks so context
    isn't lost at chunk boundaries."""
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= chunk_size:
            current = paragraph
        else:
            chunks.extend(_split_long_text(paragraph, chunk_size, overlap))

    if current:
        chunks.append(current)

    if overlap and len(chunks) > 1:
        chunks = _apply_overlap(chunks, overlap)

    return chunks


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    step = max(1, chunk_size - overlap)
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    result = [chunks[0]]
    for previous, current in zip(chunks, chunks[1:]):
        prefix = previous[-overlap:]
        result.append(f"{prefix}\n\n{current}" if prefix else current)
    return result

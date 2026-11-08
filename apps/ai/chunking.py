"""Uzun matnni RAG uchun bo'laklarga ajratish (Django'ga bog'liq emas)."""


def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    overlap = max(0, min(overlap, max_chars // 2))  # cheksiz tsikldan himoya
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    chunks: list[str] = []
    current = ""
    for line in lines:
        # Bitta qator o'zi juda uzun bo'lsa, majburan bo'lamiz
        while len(line) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:max_chars])
            line = line[max_chars - overlap:]

        if len(current) + len(line) + 1 <= max_chars:
            current = f"{current}\n{line}".strip()
        else:
            if current:
                chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks

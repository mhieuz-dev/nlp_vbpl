import re

DIEU_PATTERN = re.compile(r"(?=Điều\s+\d+\.)", re.UNICODE)
MAX_CHUNK_SIZE = 512
OVERLAP = 50

def chunk_documents(docs: list[dict]) -> list[dict]:
    chunks = []
    for doc in docs:
        content = doc["content"]
        raw_chunks = _split_by_dieu(content)
        if not raw_chunks:
            raw_chunks = _split_by_size(content)

        for i, text in enumerate(raw_chunks):
            text = text.strip()
            if not text:
                continue
            chunks.append({
                "chunk_id": f"{doc['id']}_{i}",
                "doc_id": doc["id"],
                "title": doc["title"],
                "law_type": doc["law_type"],
                "text": text,
                "char_start": content.find(text),
            })
    return chunks

def _split_by_dieu(text: str) -> list[str]:
    parts = DIEU_PATTERN.split(text)
    return [p for p in parts if p.strip()]

def _split_by_size(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start = end - OVERLAP
    return chunks

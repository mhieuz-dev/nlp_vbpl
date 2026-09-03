import re
import unicodedata

import chromadb
from src.embeddings.embedder import Embedder

_DIEU_RE = re.compile(r"^\s*Điều\s+(\d+)")

# Kho nạp từ UTS_VLC chứa mỗi bộ luật khoảng 3 lần dưới 3 cách viết tên khác
# nhau, nội dung chỉ lệch ở khoảng trắng và dấu chấm. Không khử thì top-5 bị
# các bản sao chiếm hết chỗ (đo thật: top-10 chỉ còn 4 điều khác nhau).
DEDUP_OVERFETCH = 4


def _dedup_key(text: str) -> str:
    """Khoá so trùng: bỏ dấu tiếng Việt, bỏ ký tự không phải chữ-số, lấy 160 ký tự đầu."""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:160]

class VectorStore:
    def __init__(self, embedder: Embedder, collection_name: str = "vn_legal", persist_dir: str = "./data/chroma_db"):
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    BATCH_SIZE = 500

    def insert(self, chunks: list[dict]) -> None:
        for i in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[i:i + self.BATCH_SIZE]
            texts = [c["text"] for c in batch]
            embeddings = self.embedder.embed(texts)
            self.collection.upsert(
                ids=[c["chunk_id"] for c in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "doc_id": c["doc_id"],
                    "title": c["title"],
                    "law_type": c["law_type"],
                } for c in batch],
            )
            print(f"  Indexed {min(i + self.BATCH_SIZE, len(chunks))}/{len(chunks)} chunks...")

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        query_embedding = self.embedder.embed_query(query_text)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * DEDUP_OVERFETCH,
            include=["documents", "metadatas", "distances"],
        )
        output = []
        seen = set()
        for cid, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            key = _dedup_key(doc)
            if key in seen:
                continue
            seen.add(key)
            m = _DIEU_RE.match(doc)
            output.append({
                "chunk_id": cid,
                "article": int(m.group(1)) if m else None,
                "text": doc,
                "title": meta["title"],
                "law_type": meta["law_type"],
                "score": round(1 - dist, 4),
            })
            if len(output) == top_k:
                break
        return output

import re
import chromadb
from src.embeddings.embedder import Embedder

_DIEU_RE = re.compile(r"^\s*Điều\s+(\d+)")

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
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        output = []
        for cid, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            m = _DIEU_RE.match(doc)
            output.append({
                "chunk_id": cid,
                "article": int(m.group(1)) if m else None,
                "text": doc,
                "title": meta["title"],
                "law_type": meta["law_type"],
                "score": round(1 - dist, 4),
            })
        return output

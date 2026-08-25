import chromadb
from src.embeddings.embedder import Embedder

class VectorStore:
    def __init__(self, embedder: Embedder, collection_name: str = "vn_legal", persist_dir: str = "./data/chroma_db"):
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def insert(self, chunks: list[dict]) -> None:
        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed(texts)
        self.collection.upsert(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{
                "doc_id": c["doc_id"],
                "title": c["title"],
                "law_type": c["law_type"],
            } for c in chunks],
        )

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        query_embedding = self.embedder.embed_query(query_text)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text": doc,
                "title": meta["title"],
                "law_type": meta["law_type"],
                "score": round(1 - dist, 4),
            })
        return output

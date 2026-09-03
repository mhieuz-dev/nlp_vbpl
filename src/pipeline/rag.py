from src.vectorstore.store import VectorStore
from src.generation.generator import Generator

class RAGPipeline:
    # top_k=10: đo trên 22 câu eval, Recall@k 0,864 (k=5) -> 0,955 (k=10); từ k=10
    # trở lên chững lại. Prompt chỉ dài thêm ~60%, độ trễ không đổi đáng kể.
    def __init__(self, store: VectorStore, generator: Generator, top_k: int = 10):
        self.store = store
        self.generator = generator
        self.top_k = top_k

    def ask(self, question: str) -> dict:
        chunks = self.store.query(question, top_k=self.top_k)
        result = self.generator.generate(question, chunks)
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "retrieved_chunks": chunks,
        }

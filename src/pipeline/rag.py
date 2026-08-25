from src.vectorstore.store import VectorStore
from src.generation.generator import Generator

class RAGPipeline:
    def __init__(self, store: VectorStore, generator: Generator, top_k: int = 5):
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

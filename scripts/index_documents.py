import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from src.ingestion.loader import load_legal_documents
from src.ingestion.chunker import chunk_documents
from src.embeddings.embedder import Embedder
from src.vectorstore.store import VectorStore

load_dotenv()

print("Loading documents...")
docs = load_legal_documents()
print(f"Loaded {len(docs)} documents")

print("Chunking...")
chunks = chunk_documents(docs)
print(f"Created {len(chunks)} chunks")

print("Embedding and storing in ChromaDB...")
embedder = Embedder()
store = VectorStore(embedder=embedder)
store.insert(chunks)
print("Done! ChromaDB index ready at ./data/chroma_db")

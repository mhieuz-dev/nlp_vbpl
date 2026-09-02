import pytest
from src.vectorstore.store import VectorStore
from src.embeddings.embedder import Embedder

@pytest.fixture
def store():
    embedder = Embedder()
    return VectorStore(embedder=embedder, collection_name="test_collection", persist_dir="./data/test_chroma")

SAMPLE_CHUNKS = [
    {"chunk_id": "0_0", "doc_id": "0", "title": "Bộ luật Dân sự", "law_type": "bo_luat", "text": "Điều 1. Hợp đồng là sự thỏa thuận giữa các bên.", "char_start": 0},
    {"chunk_id": "0_1", "doc_id": "0", "title": "Bộ luật Dân sự", "law_type": "bo_luat", "text": "Điều 2. Hợp đồng vô hiệu khi vi phạm điều kiện.", "char_start": 50},
]

def test_insert_and_query(store):
    store.insert(SAMPLE_CHUNKS)
    results = store.query("hợp đồng vô hiệu", top_k=1)
    assert len(results) == 1
    assert "text" in results[0]
    assert "title" in results[0]
    assert "score" in results[0]

def test_query_returns_top_k(store):
    store.insert(SAMPLE_CHUNKS)
    results = store.query("hợp đồng", top_k=2)
    assert len(results) <= 2


def test_query_returns_chunk_id_and_article(store):
    store.insert(SAMPLE_CHUNKS)
    results = store.query("hợp đồng vô hiệu", top_k=1)
    assert "chunk_id" in results[0]
    assert "article" in results[0]
    assert results[0]["article"] in (1, 2)


def test_article_is_none_when_text_has_no_dieu(store):
    store.insert([{
        "chunk_id": "9_0", "doc_id": "9", "title": "Văn bản không có điều",
        "law_type": "bo_luat", "text": "Chương I. Quy định chung.", "char_start": 0,
    }])
    results = store.query("Chương I quy định chung", top_k=1)
    assert results[0]["article"] is None

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


@pytest.fixture
def dedup_store():
    """Collection riêng để bản sao của test này không lẫn với test khác."""
    return VectorStore(
        embedder=Embedder(),
        collection_name="test_dedup",
        persist_dir="./data/test_chroma",
    )


# Cùng một Điều 407 xuất hiện 3 lần dưới 3 cách viết tên văn bản khác nhau,
# chữ khác nhau chút ở khoảng trắng/dấu chấm — đúng như kho thật.
DUPLICATE_CHUNKS = [
    {"chunk_id": "a_0", "doc_id": "a", "title": "Bộ Luật dân sự", "law_type": "code",
     "text": "Điều 407. Hợp đồng vô hiệu. 1.Quy định về giao dịch dân sự vô hiệu được áp dụng.",
     "char_start": 0},
    {"chunk_id": "b_0", "doc_id": "b", "title": "Bo Luat Dan Su", "law_type": "code",
     "text": "Điều 407. Hợp đồng vô hiệu 1. Quy định về giao dịch dân sự vô hiệu được áp dụng.",
     "char_start": 0},
    {"chunk_id": "c_0", "doc_id": "c", "title": "Bo luat dan su 2015 296215", "law_type": "code",
     "text": "Điều 407. Hợp đồng vô hiệu  1. Quy định về giao dịch dân sự vô hiệu được áp dụng.",
     "char_start": 0},
    {"chunk_id": "d_0", "doc_id": "d", "title": "Bộ luật Lao động", "law_type": "code",
     "text": "Điều 49. Hợp đồng lao động vô hiệu toàn bộ khi vi phạm quy định.",
     "char_start": 0},
]


def test_query_collapses_duplicate_articles(dedup_store):
    dedup_store.insert(DUPLICATE_CHUNKS)
    results = dedup_store.query("hợp đồng vô hiệu", top_k=3)
    dieu_407 = [r for r in results if "Điều 407" in r["text"]]
    assert len(dieu_407) == 1, "ba bản sao của Điều 407 phải gộp còn một"


def test_query_never_returns_two_copies_of_same_article(dedup_store):
    dedup_store.insert(DUPLICATE_CHUNKS)
    results = dedup_store.query("hợp đồng vô hiệu", top_k=4)
    articles = [r["article"] for r in results]
    assert len(articles) == len(set(articles)), f"kết quả còn điều trùng: {articles}"


ARTICLE_CHUNKS = [
    {"chunk_id": "ds_0", "doc_id": "ds", "title": "Bộ Luật dân sự", "law_type": "code",
     "text": "Điều 630. Di chúc hợp pháp phải có đủ các điều kiện luật định.", "char_start": 0},
    {"chunk_id": "ds_1", "doc_id": "ds", "title": "Bộ Luật dân sự", "law_type": "code",
     "text": "Điều 1. Phạm vi điều chỉnh của bộ luật này.", "char_start": 0},
    {"chunk_id": "nh_0", "doc_id": "nh", "title": "Luật Nhà ở", "law_type": "law",
     "text": "Điều 630. Quy định không liên quan gì tới di chúc.", "char_start": 0},
]


@pytest.fixture
def article_store():
    return VectorStore(
        embedder=Embedder(),
        collection_name="test_article",
        persist_dir="./data/test_chroma",
        article_lookup=True,
    )


def test_query_naming_an_article_surfaces_it_first(article_store):
    """Dense không tra được theo số điều; câu hỏi nêu đích danh phải đi đường khác."""
    article_store.insert(ARTICLE_CHUNKS)
    results = article_store.query("Điều 630 Bộ luật Dân sự nói về vấn đề gì?", top_k=3)
    assert results[0]["article"] == 630
    assert "dân sự" in results[0]["title"].lower()


def test_query_without_article_reference_is_unchanged(article_store):
    article_store.insert(ARTICLE_CHUNKS)
    results = article_store.query("di chúc hợp pháp", top_k=2)
    assert len(results) <= 2
    assert all("article" in r for r in results)

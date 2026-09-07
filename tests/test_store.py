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


@pytest.fixture
def meta_store():
    return VectorStore(embedder=Embedder(), collection_name="test_meta",
                       persist_dir="./data/test_chroma")


def test_new_metadata_round_trips(meta_store):
    meta_store.insert([{
        "chunk_id": "nd_0", "doc_id": "congbao-43733", "title": "Nghị định 168/2024/NĐ-CP",
        "law_type": "decree", "text": "Điều 6. Không chấp hành hiệu lệnh đèn tín hiệu.",
        "char_start": 0, "issue_date": "2024-12-26",
        "source_url": "https://congbao.chinhphu.vn/van-ban/x-43733.htm",
        "doc_number": "168/2024/NĐ-CP",
    }])
    got = meta_store.query("đèn tín hiệu", top_k=1)[0]
    assert got["issue_date"] == "2024-12-26"
    assert got["doc_number"] == "168/2024/NĐ-CP"
    assert got["source_url"].endswith("x-43733.htm")


def test_chunks_without_new_metadata_still_work(meta_store):
    """48.803 chunk cũ trong kho không có ba trường này, không được vỡ."""
    meta_store.insert([{
        "chunk_id": "old_0", "doc_id": "old", "title": "Bộ luật Dân sự",
        "law_type": "code", "text": "Điều 90. Quy định cũ không có metadata mới.",
        "char_start": 0,
    }])
    got = meta_store.query("quy định cũ không có metadata", top_k=1)[0]
    assert got["issue_date"] == ""
    assert got["source_url"] == ""


def test_newer_document_wins_dedup_collision():
    """NĐ hết hiệu lực và NĐ thay thế nó gần như giống hệt 160 ký tự đầu.

    Không phân xử theo ngày thì bản nào sống sót là ngẫu nhiên, và người dùng
    có thể nhận đúng mức phạt của văn bản đã bị bãi bỏ.
    """
    from src.vectorstore.store import _prefer
    cu = {"issue_date": "2019-12-30"}
    moi = {"issue_date": "2024-12-26"}
    assert _prefer(moi, cu) is True
    assert _prefer(cu, moi) is False
    # không có ngày thì không được đá văn bản có ngày ra
    assert _prefer({"issue_date": ""}, moi) is False
    assert _prefer(moi, {"issue_date": ""}) is True
    assert _prefer({"issue_date": ""}, {"issue_date": ""}) is False


@pytest.fixture
def recency_store():
    return VectorStore(embedder=Embedder(), collection_name="test_recency",
                       persist_dir="./data/test_chroma")


def test_query_keeps_newer_of_two_identical_chunks(recency_store):
    text = "Điều 6. Phạt tiền đối với hành vi không chấp hành hiệu lệnh đèn tín hiệu."
    recency_store.insert([
        {"chunk_id": "cu_0", "doc_id": "cu", "title": "Nghị định 100/2019/NĐ-CP",
         "law_type": "decree", "text": text, "char_start": 0, "issue_date": "2019-12-30"},
        {"chunk_id": "moi_0", "doc_id": "moi", "title": "Nghị định 168/2024/NĐ-CP",
         "law_type": "decree", "text": text, "char_start": 0, "issue_date": "2024-12-26"},
    ])
    got = recency_store.query("không chấp hành hiệu lệnh đèn tín hiệu", top_k=5)
    same = [c for c in got if c["text"] == text]
    assert len(same) == 1, "hai bản giống hệt phải bị gộp làm một"
    assert same[0]["issue_date"] == "2024-12-26"


def test_delete_doc_removes_all_its_chunks(meta_store):
    """Crawl lại sau khi sửa bộ lọc có thể ra ít chunk hơn; không xoá trước thì
    những chunk thừa của lần trước nằm lại vĩnh viễn."""
    chunks = [{"chunk_id": f"del_{i}", "doc_id": "todelete", "title": "Văn bản tạm",
               "law_type": "decree", "text": f"Điều {i}. Nội dung tạm để xoá.",
               "char_start": 0} for i in range(3)]
    meta_store.insert(chunks)
    assert meta_store.delete_doc("todelete") == 3
    assert meta_store.delete_doc("todelete") == 0

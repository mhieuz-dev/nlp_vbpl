from src.ingestion.chunker import MAX_CHUNK_SIZE, chunk_documents, _split_by_size

SAMPLE_DOCS = [
    {
        "id": "0",
        "title": "Bộ luật Dân sự 2015",
        "content": "Điều 1. Phạm vi điều chỉnh\nBộ luật này quy định địa vị pháp lý.\n\nĐiều 2. Đối tượng áp dụng\nBộ luật này áp dụng đối với cá nhân.",
        "law_type": "bo_luat",
    }
]

def test_chunk_returns_list():
    chunks = chunk_documents(SAMPLE_DOCS)
    assert isinstance(chunks, list)
    assert len(chunks) > 0

def test_chunk_has_required_keys():
    chunks = chunk_documents(SAMPLE_DOCS)
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "doc_id" in chunk
        assert "text" in chunk
        assert "title" in chunk
        assert "law_type" in chunk

def test_chunk_splits_by_dieu():
    chunks = chunk_documents(SAMPLE_DOCS)
    assert len(chunks) == 2

def test_chunk_text_nonempty():
    chunks = chunk_documents(SAMPLE_DOCS)
    for chunk in chunks:
        assert len(chunk["text"].strip()) > 0


# Một điều luật xử phạt thật sự dài: 20 khoản, tổng ~8.000 ký tự. Nghị định
# xử phạt giao thông có nhiều điều cỡ này nên đây không phải input bịa ra.
LONG_ARTICLE = "Điều 66. Xử phạt người điều khiển xe ô tô vi phạm quy tắc giao thông\n" + "".join(
    f"{i}. Phạt tiền từ {i} triệu đồng đến {i + 1} triệu đồng đối với người "
    f"điều khiển xe thực hiện hành vi vi phạm sau đây: {'a' * 330}\n"
    for i in range(1, 21)
)

LONG_DOCS = [
    {
        "id": "nd168",
        "title": "Nghị định 168/2024/NĐ-CP",
        "content": LONG_ARTICLE,
        "law_type": "decree",
    }
]


def test_split_by_size_terminates():
    """Bug cũ: `start = end - OVERLAP` đứng yên khi end == len(text) -> lặp vô hạn.

    Test này treo (chứ không fail) nếu bug quay lại - đó vẫn là tín hiệu đỏ.
    """
    parts = _split_by_size("a" * 1000)
    assert parts == ["a" * 1000]


def test_split_by_size_covers_whole_text():
    text = "".join(str(i % 10) for i in range(5000))
    parts = _split_by_size(text)
    assert len(parts) > 1
    assert parts[0] == text[:MAX_CHUNK_SIZE]
    assert parts[-1].endswith(text[-50:])
    assert all(len(p) <= MAX_CHUNK_SIZE for p in parts)


def test_long_article_split_into_several_chunks():
    chunks = chunk_documents(LONG_DOCS)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= MAX_CHUNK_SIZE for c in chunks)


def test_every_fragment_keeps_dieu_header():
    """ArticleIndex nhận diện chunk bằng `^\\s*Điều\\s+(\\d+)\\.` ở đầu chunk.

    Mảnh nào mất header thì vô hình với tra cứu theo số điều - tính năng đã
    nâng Recall@5 từ 0,773 lên 0,864.
    """
    chunks = chunk_documents(LONG_DOCS)
    for chunk in chunks:
        assert chunk["text"].startswith("Điều 66.")


def test_short_articles_not_resplit():
    """Điều ngắn phải đi nguyên khối, không bị cắt lẻ dù có đánh số khoản."""
    chunks = chunk_documents(SAMPLE_DOCS)
    assert len(chunks) == 2


def test_optional_metadata_is_forwarded_to_chunks():
    """issue_date/source_url/doc_number phải đi được tới vectorstore."""
    docs = [{**LONG_DOCS[0], "issue_date": "2024-12-26",
             "source_url": "https://congbao.chinhphu.vn/x.htm",
             "doc_number": "168/2024/NĐ-CP"}]
    for c in chunk_documents(docs):
        assert c["issue_date"] == "2024-12-26"
        assert c["doc_number"] == "168/2024/NĐ-CP"


def test_documents_without_optional_metadata_get_empty_strings():
    """Văn bản từ HuggingFace không có ba trường này, không được vỡ."""
    for c in chunk_documents(SAMPLE_DOCS):
        assert c["issue_date"] == ""
        assert c["source_url"] == ""

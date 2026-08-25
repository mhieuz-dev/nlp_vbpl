from src.ingestion.chunker import chunk_documents

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

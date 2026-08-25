from src.ingestion.loader import load_legal_documents

def test_load_returns_list():
    docs = load_legal_documents(max_docs=10)
    assert isinstance(docs, list)
    assert len(docs) == 10

def test_doc_has_required_keys():
    docs = load_legal_documents(max_docs=1)
    doc = docs[0]
    assert "id" in doc
    assert "title" in doc
    assert "content" in doc
    assert "law_type" in doc

def test_content_is_nonempty_string():
    docs = load_legal_documents(max_docs=1)
    assert isinstance(docs[0]["content"], str)
    assert len(docs[0]["content"]) > 0

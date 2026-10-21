"""Bản kho gọn cho Cloud Run: bỏ hai cấu trúc mà bản phục vụ không dùng.

Đo thật 21/10/2026: Cloud Run bị kill vì OOM (2056-2227 MiB trên trần 2048)
sau khi kho lên 66.563 chunk. Hệ tệp của Cloud Run nằm trong RAM nên 851 MB kho
tính vào hạn mức; bỏ chỉ mục toàn văn FTS5 và chỉ mục chuỗi của metadata còn
358 MB, kết quả truy xuất giữ nguyên.
"""
import sqlite3

import chromadb

from scripts.make_serving_corpus import slim_corpus


def _build(path, n=40):
    col = chromadb.PersistentClient(path=str(path)).get_or_create_collection(
        "vn_legal", metadata={"hnsw:space": "cosine"})
    col.upsert(
        ids=[f"c{i}" for i in range(n)],
        embeddings=[[1.0 if j == i % 4 else 0.0 for j in range(4)] for i in range(n)],
        documents=[f"Điều {i}. Nội dung số {i} " * 30 for i in range(n)],
        metadatas=[{"doc_id": f"d{i % 5}", "title": f"Luật {i % 5}"} for i in range(n)],
    )


def _tables(db):
    c = sqlite3.connect(db)
    try:
        return {r[0] for r in c.execute("select name from sqlite_master")}
    finally:
        c.close()


def test_slim_bo_fts_va_chi_muc_chuoi_nhung_giu_nguyen_truy_van(tmp_path):
    _build(tmp_path / "chroma_db")
    db = tmp_path / "chroma_db" / "chroma.sqlite3"
    truoc = db.stat().st_size
    assert "embedding_fulltext_search" in _tables(db)

    slim_corpus(tmp_path / "chroma_db")

    ten = _tables(db)
    assert "embedding_fulltext_search" not in ten
    assert "embedding_metadata_string_value" not in ten
    assert db.stat().st_size < truoc

    col = chromadb.PersistentClient(path=str(tmp_path / "chroma_db")).get_collection("vn_legal")
    assert col.count() == 40
    # truy vấn vector và lọc theo metadata (đường _dropped_docs) vẫn chạy
    assert col.query(query_embeddings=[[1.0, 0, 0, 0]], n_results=3)["ids"][0]
    assert len(col.get(where={"doc_id": "d1"})["ids"]) == 8
    # văn bản gốc còn nguyên
    assert col.get(ids=["c7"])["documents"][0].startswith("Điều 7.")


def test_slim_hai_lan_khong_loi(tmp_path):
    _build(tmp_path / "chroma_db", n=8)
    slim_corpus(tmp_path / "chroma_db")
    slim_corpus(tmp_path / "chroma_db")

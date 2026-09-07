"""Thống kê kho để hiện nhãn "dữ liệu cập nhật đến ngày ..." trên giao diện.

Dùng collection giả nên không cần embedder, không cần đọc kho thật 49.063 chunk.
"""
import json

from src.ingestion.corpus_meta import build_corpus_meta, read_meta, write_meta

ROWS = [
    {"doc_id": "a", "law_type": "code", "issue_date": ""},
    {"doc_id": "a", "law_type": "code", "issue_date": ""},
    {"doc_id": "b", "law_type": "law", "issue_date": ""},
    {"doc_id": "congbao-43733", "law_type": "decree", "issue_date": "2024-12-26"},
    {"doc_id": "congbao-470341", "law_type": "decree", "issue_date": "2026-08-22"},
]


class FakeCollection:
    """Trả metadata theo trang, đúng kiểu chromadb."""

    def __init__(self, rows, page=2):
        self.rows = rows
        self.page = page

    def count(self):
        return len(self.rows)

    def get(self, include=None, limit=None, offset=0):
        window = self.rows[offset:offset + (limit or len(self.rows))]
        return {"ids": [str(i) for i in range(len(window))], "metadatas": window}


def test_counts_chunks_documents_and_types():
    meta = build_corpus_meta(FakeCollection(ROWS))
    assert meta["chunks"] == 5
    assert meta["documents"] == 4
    assert meta["law_types"] == {"code": 2, "law": 1, "decree": 2}


def test_newest_issue_date_ignores_empty():
    """48.803 chunk cũ không có ngày; chuỗi rỗng không được thành 'mới nhất'."""
    assert build_corpus_meta(FakeCollection(ROWS))["newest_issue_date"] == "2026-08-22"


def test_no_dates_at_all_gives_none():
    rows = [{"doc_id": "a", "law_type": "law", "issue_date": ""}]
    assert build_corpus_meta(FakeCollection(rows))["newest_issue_date"] is None


def test_paginates_over_whole_collection():
    """Kho thật 49.063 chunk vượt xa một trang; không phân trang là đếm thiếu."""
    big = ROWS * 300
    meta = build_corpus_meta(FakeCollection(big, page=7), page_size=7)
    assert meta["chunks"] == len(big)
    assert meta["law_types"]["decree"] == 600


def test_write_then_read_round_trip(tmp_path):
    path = tmp_path / "corpus_meta.json"
    meta = build_corpus_meta(FakeCollection(ROWS))
    write_meta(meta, path)
    back = read_meta(path)
    assert back["newest_issue_date"] == "2026-08-22"
    assert back["last_refreshed"]  # được đóng dấu lúc ghi
    assert json.loads(path.read_text(encoding="utf-8"))["documents"] == 4


def test_read_missing_file_returns_none(tmp_path):
    """Chưa chạy refresh lần nào thì API phải trả 200 với null, không 500."""
    assert read_meta(tmp_path / "chua-co.json") is None

"""Nạp kho từ file JSON đã crawl sẵn, và chốt chặn kho teo.

Không chạm mạng, không nạp model: `refresh_corpus` import Embedder/VectorStore
muộn nên hai hàm dưới đây kiểm được mà không trả giá đó.
"""
import json

import pytest

from scripts.refresh_corpus import check_corpus_intact, load_documents

DOC = {
    "id": "congbao-43733",
    "title": "Nghị định số 168/2024/NĐ-CP",
    "content": "Điều 6. Phạt tiền từ 18.000.000 đồng.",
    "law_type": "decree",
    "issue_date": "2024-12-26",
    "doc_number": "168/2024/NĐ-CP",
    "source_url": "https://congbao.chinhphu.vn/van-ban/x-43733.htm",
    "sha256": "abc",
}


def test_load_documents_reads_json_files(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(DOC), encoding="utf-8")
    (tmp_path / "b.json").write_text(
        json.dumps({**DOC, "id": "congbao-1"}), encoding="utf-8")
    got = load_documents(tmp_path)
    assert sorted(d["id"] for d in got) == ["congbao-1", "congbao-43733"]


def test_load_documents_ignores_non_json(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(DOC), encoding="utf-8")
    (tmp_path / "ket-qua.txt").write_text("log của lượt crawl", encoding="utf-8")
    assert len(load_documents(tmp_path)) == 1


def test_load_documents_refuses_empty_dir(tmp_path):
    """Thư mục rỗng nghĩa là bước crawl hỏng, đừng lặng lẽ nạp 0 văn bản."""
    with pytest.raises(SystemExit):
        load_documents(tmp_path)


class FakeCollection:
    def __init__(self, n):
        self._n = n

    def count(self):
        return self._n


def test_intact_passes_when_corpus_matches_metadata():
    check_corpus_intact(FakeCollection(49063), {"chunks": 49063})


def test_intact_allows_small_drift():
    """Xoá vài văn bản trùng là bình thường; 5% là ngưỡng chấp nhận."""
    check_corpus_intact(FakeCollection(48000), {"chunks": 49063})


def test_intact_blocks_catastrophic_shrink():
    """Ca thật: CI mất kho cũ, Chroma mở thư mục rỗng rồi tạo kho trắng.

    Không chặn thì nó nạp vài văn bản mới, ghi corpus_meta.json là 47 chunk,
    và giao diện tự tin hiện đúng con số đó.
    """
    with pytest.raises(SystemExit, match="47"):
        check_corpus_intact(FakeCollection(47), {"chunks": 49063})


def test_intact_skips_when_no_previous_metadata():
    """Lần nạp đầu tiên chưa có metadata để so, không được chặn."""
    check_corpus_intact(FakeCollection(0), None)
    check_corpus_intact(FakeCollection(0), {})

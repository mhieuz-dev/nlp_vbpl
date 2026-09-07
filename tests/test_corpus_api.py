"""GET /api/corpus - nguồn cho nhãn "dữ liệu cập nhật đến ngày ..." trên giao diện."""
import json

from fastapi.testclient import TestClient

import server


def test_returns_meta_when_file_exists(tmp_path, monkeypatch):
    path = tmp_path / "corpus_meta.json"
    path.write_text(json.dumps({
        "chunks": 49063, "documents": 624,
        "law_types": {"law": 20000, "decree": 260},
        "newest_issue_date": "2026-08-27", "last_refreshed": "2026-09-07",
    }), encoding="utf-8")
    monkeypatch.setattr(server, "CORPUS_META_PATH", path)

    body = TestClient(server.app).get("/api/corpus").json()
    assert body["chunks"] == 49063
    assert body["newest_issue_date"] == "2026-08-27"
    assert body["law_types"]["decree"] == 260


def test_returns_200_with_null_when_never_refreshed(tmp_path, monkeypatch):
    """Chưa chạy refresh lần nào không phải là lỗi máy chủ."""
    monkeypatch.setattr(server, "CORPUS_META_PATH", tmp_path / "chua-co.json")
    res = TestClient(server.app).get("/api/corpus")
    assert res.status_code == 200
    assert res.json() is None


def test_ask_explains_itself_when_corpus_is_missing(monkeypatch):
    """Kho chưa sẵn sàng phải trả 503 kèm lời giải thích, không phải 500 trần.

    Đo trên ảnh Docker thật: thiếu kho thì ensure_corpus ném RuntimeError trong
    get_pipeline, tức là ở tầng Depends - TRƯỚC thân route - nên
    _error_message() không bao giờ chạy tới và người dùng chỉ thấy
    "Internal Server Error".
    """
    def khong_co_kho(*a, **kw):
        raise RuntimeError("Không có kho ở data/chroma_db và cũng không đặt CHROMA_REPO_ID.")

    monkeypatch.setattr(server, "ensure_corpus", khong_co_kho)
    monkeypatch.setattr(server, "_pipeline", None)
    res = TestClient(server.app, raise_server_exceptions=False).post(
        "/api/ask", json={"question": "vượt đèn đỏ phạt bao nhiêu"})
    assert res.status_code == 503
    assert "kho" in res.json()["detail"].lower()

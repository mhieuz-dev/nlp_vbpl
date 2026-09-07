"""Tải kho Chroma về lúc khởi động, cho bản deploy.

Đĩa của HF Space là tạm: restart là mất. Kho 612 MB nên không nhét vào git
được, phải để ở HuggingFace Dataset rồi tải về mỗi lần container khởi động.
Test dùng hàm tải giả nên không chạm mạng.
"""
import pytest

from src.vectorstore.bootstrap import ensure_corpus


class FakeDownloader:
    """Giả lập snapshot_download: tạo thư mục rồi trả đường dẫn."""

    def __init__(self):
        self.calls = []

    def __call__(self, repo_id, local_dir, **kw):
        self.calls.append((repo_id, str(local_dir)))
        from pathlib import Path
        p = Path(local_dir)
        (p / "chroma.sqlite3").parent.mkdir(parents=True, exist_ok=True)
        (p / "chroma.sqlite3").write_bytes(b"gia lap")
        return str(p)


def test_downloads_when_corpus_missing(tmp_path):
    dl = FakeDownloader()
    got = ensure_corpus(tmp_path / "chroma_db", repo_id="ai/kho", download=dl)
    assert (got / "chroma.sqlite3").exists()
    assert dl.calls == [("ai/kho", str(tmp_path / "chroma_db"))]


def test_skips_download_when_corpus_already_there(tmp_path):
    """Chạy ở máy cá nhân đã có sẵn kho 612 MB - đừng tải lại."""
    local = tmp_path / "chroma_db"
    local.mkdir()
    (local / "chroma.sqlite3").write_bytes(b"kho that")
    dl = FakeDownloader()
    got = ensure_corpus(local, repo_id="ai/kho", download=dl)
    assert dl.calls == [], "đã có kho thì không được gọi tải"
    assert (got / "chroma.sqlite3").read_bytes() == b"kho that"


def test_empty_directory_counts_as_missing(tmp_path):
    """Thư mục rỗng do mount volume tạo ra không phải là kho."""
    local = tmp_path / "chroma_db"
    local.mkdir()
    dl = FakeDownloader()
    ensure_corpus(local, repo_id="ai/kho", download=dl)
    assert len(dl.calls) == 1


def test_no_repo_id_means_local_only(tmp_path):
    """Chạy ở máy cá nhân không đặt biến môi trường: báo lỗi rõ ràng thay vì
    lặng lẽ khởi động với kho rỗng rồi trả lời sai cho mọi câu hỏi."""
    with pytest.raises(RuntimeError, match="CHROMA_REPO_ID"):
        ensure_corpus(tmp_path / "khong-co", repo_id=None, download=FakeDownloader())

"""Tải kho Chroma về đĩa cục bộ lúc khởi động, cho bản deploy.

Đĩa của Cloud Run instance là tạm và scale-to-zero là mất; kho 620 MB không
nhét vào git được. Nên kho là một tarball .tar.gz trên GCS, tải qua HTTPS
thường mỗi lần khởi động nguội. Ở máy cá nhân kho đã nằm sẵn trong data/ nên
hàm này không làm gì.

`fetch` tiêm vào nên test không chạm mạng.
"""
import io
import tarfile

import pytest

from src.vectorstore.bootstrap import ensure_corpus


def _make_tar_gz(files: dict) -> bytes:
    """Dựng một tarball .tar.gz trong bộ nhớ, giống thứ CI đẩy lên GCS.

    Dùng gzip chứ không phải zstd: tarfile của Python hỗ trợ sẵn, không phải
    thêm thư viện vào bản deploy, và chênh lệch dung lượng (~370 vs ~340 MB)
    không đáng so với thời gian tải.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return raw.getvalue()


class FakeFetch:
    """Trả bytes của tarball dựng sẵn, ghi lại URL đã gọi."""

    def __init__(self, blob: bytes):
        self.blob = blob
        self.calls = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        return self.blob


SAMPLE = {"chroma_db/chroma.sqlite3": b"noi dung kho",
          "corpus_meta.json": b'{"chunks": 49063}'}


def test_downloads_and_extracts_when_corpus_missing(tmp_path):
    fetch = FakeFetch(_make_tar_gz(SAMPLE))
    got = ensure_corpus(tmp_path, url="https://x/corpus.tar.gz", fetch=fetch)
    assert (got / "chroma_db" / "chroma.sqlite3").read_bytes() == b"noi dung kho"
    assert (got / "corpus_meta.json").exists()
    assert fetch.calls == ["https://x/corpus.tar.gz"]


def test_skips_download_when_corpus_already_there(tmp_path):
    """Chạy ở máy cá nhân đã có kho - đừng tải lại."""
    (tmp_path / "chroma_db").mkdir()
    (tmp_path / "chroma_db" / "chroma.sqlite3").write_bytes(b"kho that o may")
    fetch = FakeFetch(b"")
    ensure_corpus(tmp_path, url="https://x/corpus.tar.gz", fetch=fetch)
    assert fetch.calls == []
    assert (tmp_path / "chroma_db" / "chroma.sqlite3").read_bytes() == b"kho that o may"


def test_empty_chroma_dir_counts_as_missing(tmp_path):
    """Thư mục rỗng không phải là kho."""
    (tmp_path / "chroma_db").mkdir()
    fetch = FakeFetch(_make_tar_gz(SAMPLE))
    ensure_corpus(tmp_path, url="https://x/corpus.tar.gz", fetch=fetch)
    assert len(fetch.calls) == 1


def test_no_url_and_no_local_corpus_raises_clearly(tmp_path):
    """Không có kho mà cũng không đặt CORPUS_URL: chết ngay với thông báo rõ,
    thà vậy còn hơn khởi động êm với kho rỗng rồi trả lời sai mọi câu."""
    with pytest.raises(RuntimeError, match="CORPUS_URL"):
        ensure_corpus(tmp_path, url=None, fetch=FakeFetch(b""))

"""Bảo đảm có kho Chroma trên đĩa cục bộ trước khi phục vụ câu hỏi.

Vì sao cần: đĩa của Cloud Run instance là tạm, scale-to-zero rồi khởi động lại
là mất; mà kho 620 MB thì không nhét vào git được. Nên kho là một tarball
`.tar.gz` trên Google Cloud Storage (`CORPUS_URL`), tải qua HTTPS thường mỗi lần
khởi động nguội rồi giải nén xuống đĩa. Object để public nên app không cần SDK
hay credential - kho chỉ là văn bản luật từ nguồn nhà nước công khai.

Ở máy cá nhân thì kho đã nằm sẵn trong `data/` nên hàm này không làm gì.
"""
import io
import os
import tarfile
from pathlib import Path

DEFAULT_LOCAL_DIR = Path("data")
CHUNK = 1 << 20


def _http_get(url: str) -> bytes:
    import requests

    res = requests.get(url, timeout=300, stream=True)
    res.raise_for_status()
    buf = io.BytesIO()
    for part in res.iter_content(CHUNK):
        buf.write(part)
    return buf.getvalue()


def ensure_corpus(local_dir=DEFAULT_LOCAL_DIR, url=None, fetch=None) -> Path:
    """Trả về thư mục chứa kho, tải tarball từ `CORPUS_URL` nếu chưa có.

    `fetch` tiêm vào để test khỏi chạm mạng; mặc định là một GET qua `requests`.
    Kho coi là "đã có" khi `local_dir/chroma_db` tồn tại và không rỗng.
    """
    local_dir = Path(local_dir)
    chroma_dir = local_dir / "chroma_db"
    if chroma_dir.is_dir() and any(chroma_dir.iterdir()):
        return local_dir

    url = url or os.getenv("CORPUS_URL")
    if not url:
        # Thà chết ngay còn hơn khởi động êm với kho rỗng rồi trả lời sai mọi câu.
        raise RuntimeError(
            f"Không có kho ở {chroma_dir} và cũng không đặt CORPUS_URL. "
            "Ở máy cá nhân thì chạy scripts/index_documents.py; trên bản deploy "
            "thì đặt CORPUS_URL trỏ tới tarball .tar.gz của kho trên GCS."
        )

    blob = (fetch or _http_get)(url)
    local_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        tar.extractall(local_dir)
    return local_dir

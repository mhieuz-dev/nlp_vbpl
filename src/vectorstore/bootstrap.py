"""Bảo đảm có kho Chroma trước khi phục vụ câu hỏi.

Vì sao cần: đĩa của HuggingFace Space là tạm, restart là mất; mà kho 612 MB thì
không nhét vào git được. Nên kho ở một HuggingFace Dataset repo, tải về mỗi lần
container khởi động. Ở máy cá nhân thì kho đã nằm sẵn trong `data/` nên hàm này
không làm gì cả.
"""
import os
from pathlib import Path

DEFAULT_LOCAL_DIR = Path("data/chroma_db")


def ensure_corpus(local_dir=DEFAULT_LOCAL_DIR, repo_id=None, download=None) -> Path:
    """Trả về thư mục kho, tải từ HuggingFace Dataset nếu chưa có.

    `download` tiêm vào để test khỏi chạm mạng; mặc định là
    `huggingface_hub.snapshot_download`.
    """
    local_dir = Path(local_dir)
    if any(local_dir.glob("*")) if local_dir.exists() else False:
        return local_dir

    repo_id = repo_id or os.getenv("CHROMA_REPO_ID")
    if not repo_id:
        # Thà chết ngay còn hơn khởi động êm với kho rỗng rồi trả lời sai mọi câu.
        raise RuntimeError(
            f"Không có kho ở {local_dir} và cũng không đặt CHROMA_REPO_ID. "
            "Ở máy cá nhân thì chạy scripts/index_documents.py; trên bản deploy "
            "thì đặt CHROMA_REPO_ID trỏ tới HuggingFace Dataset chứa kho."
        )

    if download is None:
        from huggingface_hub import snapshot_download as download

    local_dir.mkdir(parents=True, exist_ok=True)
    download(repo_id=repo_id, local_dir=local_dir, repo_type="dataset",
             token=os.getenv("HF_TOKEN"))
    return local_dir

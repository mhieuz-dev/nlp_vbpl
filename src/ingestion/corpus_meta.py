"""Thống kê kho, để giao diện nói được "dữ liệu cập nhật đến ngày nào".

Đặt ở GỐC REPO chứ không phải trong `data/`: `.gitignore` có `data/` nên file
nằm trong đó sẽ không lên git, mà bản deploy cần đọc được nó.
"""
import json
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "corpus_meta.json"
PAGE_SIZE = 5000


def build_corpus_meta(collection, page_size: int = PAGE_SIZE) -> dict:
    """Quét toàn bộ metadata của collection. Chỉ chạy lúc refresh, không lúc hỏi."""
    total = collection.count()
    documents, law_types, newest = set(), {}, ""
    offset = 0
    while offset < total:
        page = collection.get(include=["metadatas"], limit=page_size, offset=offset)
        for meta in page["metadatas"]:
            documents.add(meta.get("doc_id", ""))
            key = meta.get("law_type", "other")
            law_types[key] = law_types.get(key, 0) + 1
            # Chuỗi rỗng của 48.803 chunk cũ không được thành "mới nhất".
            issued = meta.get("issue_date", "")
            if issued > newest:
                newest = issued
        offset += page_size
    return {
        "chunks": total,
        "documents": len(documents),
        "law_types": law_types,
        "newest_issue_date": newest or None,
    }


def write_meta(meta: dict, path=DEFAULT_PATH) -> Path:
    path = Path(path)
    meta = {**meta, "last_refreshed": date.today().isoformat()}
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_meta(path=DEFAULT_PATH):
    """None khi chưa chạy refresh lần nào - để API trả 200 chứ không 500."""
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

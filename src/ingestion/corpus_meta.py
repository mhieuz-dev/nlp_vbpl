"""Thống kê kho, để giao diện nói được "dữ liệu cập nhật đến ngày nào".

Hai chỗ file này có thể nằm:
- `data/corpus_meta.json` - đi kèm kho, đóng vào cùng tarball. Đây là nguồn thật
  cho bản deploy và cho lượt cập nhật hằng đêm, vì nó luôn khớp với kho hiện tại.
- `<gốc repo>/corpus_meta.json` - bản committed, làm mồi cho lần chạy đầu và cho
  máy cá nhân. Có thể tụt hậu so với kho deploy nên chỉ dùng khi không có bản kia.

`read_meta` ưu tiên bản trong `data/`. Nếu không thì nhãn "cập nhật đến ngày..."
sẽ đứng yên ở ngày commit dù kho deploy đã đổi - đúng thứ file này sinh ra để tránh.
"""
import json
from datetime import date
from pathlib import Path

DATA_PATH = Path("data/corpus_meta.json")
REPO_PATH = Path(__file__).resolve().parents[2] / "corpus_meta.json"
DEFAULT_PATH = REPO_PATH  # giữ tên cũ cho chỗ khác đang import
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


def write_meta(meta: dict, path=None) -> Path:
    """Ghi metadata. Không truyền path thì ghi vào `data/` nếu thư mục đó tồn tại
    (lượt cập nhật hằng đêm cần nó ở đây để đóng vào tarball), còn không thì ghi
    ra gốc repo (máy cá nhân, để commit làm mồi)."""
    if path is not None:
        target = Path(path)
    elif DATA_PATH.parent.is_dir():
        target = DATA_PATH
    else:
        target = REPO_PATH
    meta = {**meta, "last_refreshed": date.today().isoformat()}
    target.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target


def read_meta(path=None):
    """None khi chưa có metadata ở đâu cả - để API trả 200 chứ không 500.

    Không truyền path thì thử `data/corpus_meta.json` (khớp kho deploy) trước,
    rồi mới tới bản committed ở gốc repo.
    """
    candidates = [Path(path)] if path is not None else [DATA_PATH, REPO_PATH]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None

"""Rút gọn kho Chroma cho bản phục vụ trên Cloud Run.

Vì sao cần: hệ tệp của Cloud Run nằm trong RAM và tính vào hạn mức bộ nhớ. Kho
đầy đủ 851 MB (66.563 chunk) cộng tiến trình ~1,48 GB là 2,33 GB, vượt trần
2 GiB và container bị kill liên tục (log 21/10/2026). Hai thứ dưới đây là
phần thừa của bản phục vụ, cắt đi còn 358 MB:

  embedding_fulltext_search     FTS5 trigram, 274 MB. Chỉ phục vụ where_document,
                                app không bao giờ gọi.
  embedding_metadata_string_value  chỉ mục (key, string_value), ~217 MB, nhân đôi
                                cả văn bản điều luật. Chỉ để lọc metadata nhanh;
                                app chỉ lọc theo doc_id với limit=1 nên quét
                                tuần tự 67 nghìn dòng vẫn tức thì.

CHỈ chạy trên bản sao để phục vụ. Kho dùng để nạp thêm văn bản (current.tar.gz)
phải giữ đủ: Chroma ghi vào bảng FTS mỗi lần upsert, thiếu là lỗi.
Đo trên 42 câu eval: kết quả giống hệt bản đầy đủ.
"""
import sqlite3
import sys
from pathlib import Path


def slim_corpus(chroma_dir) -> None:
    db = Path(chroma_dir) / "chroma.sqlite3"
    conn = sqlite3.connect(db)
    try:
        conn.execute("DROP TABLE IF EXISTS embedding_fulltext_search")
        conn.execute("DROP INDEX IF EXISTS embedding_metadata_string_value")
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


if __name__ == "__main__":
    slim_corpus(sys.argv[1])

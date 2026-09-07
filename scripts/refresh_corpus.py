"""Cập nhật kho từ Công báo điện tử.

    # hàng ngày: văn bản mới trong RSS
    python scripts/refresh_corpus.py --recent

    # backfill có chủ đích: dò một dải id, chỉ lấy nghị định
    python scripts/refresh_corpus.py --sweep 43550 43960 --types decree

    # xem trước, không embed, không ghi kho
    python scripts/refresh_corpus.py --recent --dry-run

Logic nằm hết trong `src/ingestion/congbao.py`; file này chỉ nối tham số.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.chunker import chunk_documents
from src.ingestion.congbao import Crawler, http_fetcher
from src.ingestion.corpus_meta import build_corpus_meta, write_meta

STATE_PATH = "data/congbao_state.json"
CACHE_DIR = "data/cache/congbao"

# Trần cứng. Kho phình lên thì thời gian TẢI lúc khởi động mới là thứ giết bản
# deploy free, chứ không phải RAM: ~12,5 KB/chunk, 49.063 chunk đã là 612 MB.
MAX_NEW_CHUNKS = 40000


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recent", action="store_true", help="văn bản mới trong RSS")
    mode.add_argument("--sweep", nargs=2, type=int, metavar=("LO", "HI"),
                      help="dò dải id văn bản (mỗi lần tra tải 0 byte)")
    ap.add_argument("--types", default="", help="lọc loại, ví dụ: decree,circular")
    ap.add_argument("--max-docs", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true",
                    help="chỉ crawl và cắt chunk, KHÔNG nạp mô hình, KHÔNG ghi kho")
    args = ap.parse_args(argv)

    law_types = {t.strip() for t in args.types.split(",") if t.strip()} or None
    crawler = Crawler(fetch=http_fetcher(), state_path=STATE_PATH, cache_dir=CACHE_DIR)

    if args.recent:
        docs = crawler.crawl_recent(max_docs=args.max_docs, law_types=law_types)
    else:
        docs = crawler.crawl_ids(range(args.sweep[0], args.sweep[1] + 1),
                                 max_docs=args.max_docs, law_types=law_types)

    print(f"\ncrawl: {len(docs)} văn bản mới")
    for d in docs:
        print(f"  {d['id']:20} {d['law_type']:12} {d['issue_date'] or '-':12} "
              f"{len(d['content']):>8} ký tự  {d['title'][:52]}")
    if not docs:
        print("Không có gì mới.")
        return 0

    chunks = chunk_documents(docs)
    print(f"chunk: {len(chunks)}")
    if len(chunks) > MAX_NEW_CHUNKS:
        print(f"DỪNG: {len(chunks)} chunk vượt trần {MAX_NEW_CHUNKS}. "
              "Thu hẹp --sweep hoặc --max-docs.")
        return 1

    if args.dry_run:
        print("--dry-run: dừng ở đây, không nạp mô hình, không ghi kho.")
        return 0

    # Import muộn: --dry-run không phải trả giá nạp torch + e5-base.
    from src.embeddings.embedder import Embedder
    from src.vectorstore.store import VectorStore

    store = VectorStore(embedder=Embedder(), article_lookup=False)
    before = store.collection.count()
    # Xoá trước khi nạp: upsert chỉ ghi đè theo chunk_id, lần crawl sau ra ít
    # chunk hơn thì phần dư của lần trước nằm lại vĩnh viễn.
    for doc in docs:
        store.delete_doc(doc["id"])
    store.insert(chunks)
    print(f"kho: {before} -> {store.collection.count()} chunk")

    path = write_meta(build_corpus_meta(store.collection))
    print(f"đã ghi {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

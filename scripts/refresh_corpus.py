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
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.chunker import chunk_documents
from src.ingestion.congbao import Crawler, http_fetcher
from src.ingestion.corpus_meta import build_corpus_meta, read_meta, write_meta

STATE_PATH = "data/congbao_state.json"
CACHE_DIR = "data/cache/congbao"

# Trần cứng. Kho phình lên thì thời gian TẢI lúc khởi động mới là thứ giết bản
# deploy free, chứ không phải RAM: ~12,5 KB/chunk, 49.063 chunk đã là 612 MB.
MAX_NEW_CHUNKS = 40000


# Kho mở ra được phép nhỏ hơn metadata bao nhiêu trước khi coi là hỏng. Xoá vài
# văn bản trùng là bình thường; mất 5% trở lên nghĩa là kho không nạp được đúng.
SHRINK_TOLERANCE = 0.95


def load_documents(directory) -> list[dict]:
    """Đọc các văn bản đã crawl sẵn từ thư mục JSON.

    Vì sao cần: crawler ghi `status:"ok"` vào state NGAY sau khi tải xong
    (congbao.py:320), còn `--dry-run` thoát trước bước nạp. Nên nếu lượt tự
    động dò bằng --dry-run rồi crawl lại để nạp, lần crawl thứ hai thấy mọi
    văn bản đều "ok" và trả về rỗng - pipeline báo xanh mãi mà không nạp gì.
    Cách sửa là crawl đúng một lần, ghi ra --save-dir, rồi nạp từ đó.
    """
    directory = Path(directory)
    docs = [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(directory.glob("*.json"))]
    if not docs:
        raise SystemExit(f"DỪNG: {directory}/ không có file JSON nào. "
                         "Bước crawl hỏng, hoặc chỉ đường dẫn sai.")
    return docs


def check_corpus_intact(collection, previous_meta) -> None:
    """Kho vừa mở phải khớp với corpus_meta.json đi kèm nó.

    Ca cần chặn: CI không tải được kho cũ, `chromadb.PersistentClient` mở một
    thư mục rỗng và VUI VẺ tạo kho mới trắng tinh. Nạp vài văn bản mới vào rồi
    ghi metadata là 47 chunk, giao diện hiện đúng 47, và 49.063 chunk cũ biến
    mất mà không ai biết. Phải chặn TRƯỚC khi nạp.
    """
    expected = (previous_meta or {}).get("chunks", 0)
    if not expected:
        return  # lần đầu, chưa có gì để so
    actual = collection.count()
    if actual < expected * SHRINK_TOLERANCE:
        raise SystemExit(
            f"DỪNG: kho mở ra chỉ có {actual} chunk nhưng corpus_meta.json ghi "
            f"{expected}. Nhiều khả năng kho cũ không tải được và Chroma vừa "
            "tạo một kho rỗng. Không nạp gì cả để khỏi ghi đè kho thật."
        )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recent", action="store_true", help="văn bản mới trong RSS")
    mode.add_argument("--sweep", nargs=2, type=int, metavar=("LO", "HI"),
                      help="dò dải id văn bản (mỗi lần tra tải 0 byte)")
    mode.add_argument("--ingest-dir", metavar="DIR",
                      help="nạp các văn bản JSON đã crawl sẵn, KHÔNG crawl lại")
    ap.add_argument("--types", default="", help="lọc loại, ví dụ: decree,circular")
    ap.add_argument("--max-docs", type=int, default=50)
    ap.add_argument("--save-dir", metavar="DIR",
                    help="ghi mỗi văn bản crawl được ra một file JSON, để lượt "
                         "chạy tự động có thứ giữ lại mà không cần tải lại")
    ap.add_argument("--dry-run", action="store_true",
                    help="chỉ crawl và cắt chunk, KHÔNG nạp mô hình, KHÔNG ghi kho")
    args = ap.parse_args(argv)

    law_types = {t.strip() for t in args.types.split(",") if t.strip()} or None

    if args.ingest_dir:
        docs = load_documents(args.ingest_dir)
        print(f"\nnạp lại: {len(docs)} văn bản từ {args.ingest_dir}/")
    else:
        crawler = Crawler(fetch=http_fetcher(), state_path=STATE_PATH,
                          cache_dir=CACHE_DIR)
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

    if args.save_dir:
        out = Path(args.save_dir)
        out.mkdir(parents=True, exist_ok=True)
        for d in docs:
            (out / f"{d['id']}.json").write_text(
                json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã ghi {len(docs)} file vào {out}/")

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
    check_corpus_intact(store.collection, read_meta())
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

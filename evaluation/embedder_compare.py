"""So embedder trên CÙNG kho và CÙNG 42 câu với cấu hình app (từ điển, tra số Điều, khử trùng).

    python -m evaluation.embedder_compare --model keepitreal/vietnamese-sbert

Nhúng lại toàn bộ chunk của kho chính vào một kho riêng (mặc định
data/chroma_cmp, ~2 giờ trên CPU cho 53 nghìn chunk). Chạy lại thì nối tiếp
phần còn thiếu, không nhúng lại từ đầu. Kết quả ghi thêm vào
evaluation/ablation_results.json, khoá "embedders".

Lần so trước (evaluation/model_comparison.json) chấm bằng điểm tương đồng trung
bình trên 10 câu dễ: điểm cosine của hai model khác nhau không so được với nhau,
nên con số đó không nói model nào tìm đúng hơn. Ở đây chấm bằng Recall/MRR.
"""
import argparse
import json
import time

import torch

from evaluation.ablation import RESULTS_PATH, _measure, _table, compare_ranks, load_chunks
from src.embeddings.embedder import Embedder


class PlainEmbedder(Embedder):
    """Model không dùng tiền tố "query: "/"passage: " (tiền tố đó là quy ước riêng của e5)."""

    def embed(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, query):
        return self.model.encode(query, normalize_embeddings=True).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--persist", default="data/chroma_cmp")
    ap.add_argument("--threads", type=int, default=8,
                    help="giới hạn luồng CPU để máy vẫn dùng được trong lúc nhúng")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)

    from evaluation.retrieval_dataset import COLLOQUIAL_QUESTIONS, RETRIEVAL_QUESTIONS
    from src.pipeline.rag import RAGPipeline, build_store
    from src.pipeline.relations import SUPERSEDED
    from src.vectorstore.store import VectorStore

    main_store = build_store(Embedder())
    chunks = load_chunks(main_store)
    cmp_emb = PlainEmbedder(args.model)
    cmp_store = VectorStore(cmp_emb, persist_dir=args.persist, article_lookup=True,
                            superseded=SUPERSEDED)

    have = set()
    for off in range(0, cmp_store.collection.count(), 5000):
        have |= set(cmp_store.collection.get(offset=off, limit=5000, include=[])["ids"])
    todo = [c for c in chunks if c["chunk_id"] not in have]
    print(f"{args.model}: kho chính {len(chunks)} chunk, đã có {len(have)}, cần nhúng {len(todo)}")
    t = time.perf_counter()
    cmp_store.insert(todo)
    print(f"nhúng xong sau {(time.perf_counter() - t) / 60:.0f} phút")

    qs = RETRIEVAL_QUESTIONS + COLLOQUIAL_QUESTIONS
    rows = [("multilingual-e5-base (app)", _measure(RAGPipeline(main_store, None), qs)),
            (args.model, _measure(RAGPipeline(cmp_store, None), qs))]
    rows[1][1]["vs_full"] = compare_ranks(rows[0][1], rows[1][1])
    print(_table(rows))

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.exists() else {}
    results.setdefault("embedders", {}).update(dict(rows))
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"đã ghi {RESULTS_PATH}")


if __name__ == "__main__":
    main()

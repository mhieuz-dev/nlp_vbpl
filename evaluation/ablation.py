"""Thí nghiệm cắt bỏ (ablation) phần truy xuất: mỗi thành phần đóng góp bao nhiêu.

    python -m evaluation.ablation              # bảng thành phần + top_k, không gọi LLM
    python -m evaluation.ablation --followup   # thêm so cách xử lý câu nối tiếp (gọi Groq)

Mọi cấu hình chạy qua đúng `evaluate_retrieval` của bộ đánh giá chính (42 câu,
chấm phiên bản văn bản + Điều + đoạn bằng chứng), chỉ thay kho hoặc bật/tắt một
bước. BM25 và hybrid CHỈ là thí nghiệm, app không dùng.

Kết quả ghi ra evaluation/ablation_results.json để báo cáo trích số, không chép tay.
"""
import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

from evaluation.retrieval_eval import chunk_matches, evaluate_retrieval
from src.vectorstore.store import DEDUP_OVERFETCH, _dedup_key, _prefer

RESULTS_PATH = Path("evaluation/ablation_results.json")
KS = (1, 3, 5, 10, 15)

_TOKEN_RE = re.compile(r"[^\W_]+")


def tokenize(text: str) -> list[str]:
    """Tách âm tiết, giữ dấu (dấu phân biệt nghĩa: "phạt" khác "phát") và chữ số."""
    return _TOKEN_RE.findall(text.lower())


def dedup_top(chunks: list[dict], top_k: int) -> list[dict]:
    """Khử trùng theo đúng luật của VectorStore.query, cho các kho thí nghiệm."""
    out, seen = [], {}
    for c in chunks:
        key = _dedup_key(c["text"])
        pos = seen.get(key)
        if pos is None:
            seen[key] = len(out)
            out.append(c)
        elif _prefer(c, out[pos]):
            out[pos] = c
        if len(out) == top_k:
            break
    return out


def rrf_merge(lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: điểm = tổng 1/(k + hạng) qua các danh sách.

    Cộng theo KHOÁ KHỬ TRÙNG, không theo chunk_id: kho có 2-3 bản sao mỗi bộ
    luật, dense lấy bản này còn BM25 lấy bản kia của cùng một điều. Cộng theo
    chunk_id thì điều đó bị tách đôi, không bao giờ được cộng dồn - lượt đo đầu
    cho hybrid R@5 0,52, tệ hơn cả hai thành phần.
    """
    score, best = {}, {}
    for lst in lists:
        for rank, c in enumerate(lst, start=1):
            key = _dedup_key(c["text"])
            score[key] = score.get(key, 0.0) + 1.0 / (k + rank)
            if key not in best or _prefer(c, best[key]):
                best[key] = c
    return [best[key] for key in sorted(best, key=lambda key: -score[key])]


class BM25Index:
    """BM25 trên unigram + bigram âm tiết (từ tiếng Việt phần lớn là hai âm tiết).

    Dựng bằng ma trận thưa: trọng số tf đã chuẩn hoá theo độ dài được tính sẵn,
    nên một truy vấn chỉ là một phép nhân cột với idf.
    """

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.vec = CountVectorizer(tokenizer=tokenize, lowercase=False,
                                   token_pattern=None, ngram_range=(1, 2))
        tf = self.vec.fit_transform([c["text"] for c in chunks]).tocoo()
        n = tf.shape[0]
        dl = np.bincount(tf.row, weights=tf.data, minlength=n)
        df = np.bincount(tf.col, minlength=tf.shape[1])
        self.idf = np.log(1 + (n - df + 0.5) / (df + 0.5))
        w = tf.data * (k1 + 1) / (tf.data + k1 * (1 - b + b * dl[tf.row] / dl.mean()))
        self.w = sparse.csc_matrix((w.astype(np.float32), (tf.row, tf.col)), shape=tf.shape)

    def search(self, query: str, n: int) -> list[dict]:
        cols = self.vec.transform([query]).indices
        if not len(cols):
            return []
        scores = np.asarray(self.w[:, cols] @ self.idf[cols]).ravel()
        n = min(n, len(scores))
        top = np.argpartition(-scores, n - 1)[:n]
        top = top[np.argsort(-scores[top])]
        return [dict(self.chunks[i], score=round(float(scores[i]), 4))
                for i in top if scores[i] > 0]


class BM25Store:
    """Kho thí nghiệm cùng giao diện query() với VectorStore."""

    def __init__(self, index: BM25Index, dropped: set):
        self.index, self.dropped = index, dropped

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        got = [c for c in self.index.search(query_text, top_k * DEDUP_OVERFETCH)
               if c["doc_id"] not in self.dropped]
        return dedup_top(got, top_k)


class HybridStore:
    """Dense (đường app, có tra số Điều) trộn BM25 bằng RRF, rồi khử trùng."""

    def __init__(self, dense, bm25: BM25Store, pool: int = 60, k: int = 60):
        self.dense, self.bm25, self.pool, self.k = dense, bm25, pool, k

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        merged = rrf_merge([self.dense.query(query_text, top_k=self.pool),
                            self.bm25.query(query_text, top_k=self.pool)], k=self.k)
        return dedup_top(merged, top_k)


def load_chunks(store) -> list[dict]:
    """Toàn bộ chunk của kho, đúng định dạng VectorStore trả về."""
    out, col, step = [], store.collection, 5000
    for off in range(0, col.count(), step):
        got = col.get(offset=off, limit=step, include=["documents", "metadatas"])
        out += [store._to_chunk(cid, doc, meta, 0.0)
                for cid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"])]
    return out


def _measure(pipeline, questions) -> dict:
    # Làm nóng: câu đầu nêu "Điều N" dựng chỉ mục số điều (~9s) một lần cho mỗi kho.
    pipeline.retrieve("Điều 1 Bộ luật Dân sự", fit=False)
    t = time.perf_counter()
    m = evaluate_retrieval(pipeline, questions, ks=KS)
    m["ms_per_query"] = round((time.perf_counter() - t) * 1000 / len(questions))
    # Số điều KHÁC NHAU trong danh sách: đo cái khử trùng mua được, Recall không thấy.
    m["distinct_in_list"] = round(float(np.mean([
        len({_dedup_key(c["text"]) for c in pipeline.retrieve(q["question"], fit=False)})
        for q in questions])), 2)
    return m


def compare_ranks(base: dict, other: dict) -> dict:
    """Đếm câu có hạng tốt lên / xấu đi so với cấu hình gốc (ngoài danh sách = vô cực).

    42 câu thì lệch một câu đã là 0,024 Recall; cột này cho biết chênh lệch đến
    từ bao nhiêu câu, tránh đọc một câu may rủi thành một kết luận.
    """
    inf = float("inf")
    pairs = [(a["rank"] or inf, b["rank"] or inf)
             for a, b in zip(base["per_question"], other["per_question"])]
    return {"better": sum(b < a for a, b in pairs), "worse": sum(b > a for a, b in pairs)}


def _row(name: str, m: dict) -> str:
    cells = [f"{m[f'recall_at_{k}']:.4f}" for k in KS]
    cmp = m.get("vs_full", {"better": 0, "worse": 0})
    return (f"| {name} | " + " | ".join(cells) + f" | {m['mrr']:.4f} | {m['in_context']:.4f} "
            f"| +{cmp['better']} / -{cmp['worse']} | {m['distinct_in_list']} | {m['ms_per_query']} |")


def _table(rows) -> str:
    head = (["Cấu hình"] + [f"R@{k}" for k in KS]
            + ["MRR", "Trong context", "Câu tốt lên / xấu đi", "Điều khác nhau / danh sách",
               "ms/câu"])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    return "\n".join(lines + [_row(name, m) for name, m in rows])


def followup_ablation(store, generator) -> dict:
    """So 3 cách tìm cho câu nối tiếp trong bộ nghiệm thu: nguyên câu, ghép câu
    trước, viết lại bằng LLM (cách app dùng). Hạng tính trên top-15."""
    from evaluation.acceptance_dataset import ACCEPTANCE
    from src.pipeline.followup import _ghep
    from src.pipeline.synonyms import expand_query

    items = [x for x in ACCEPTANCE if x.get("history")]
    modes = {
        "nguyên câu": lambda q, h: q,
        "ghép câu trước": _ghep,
        "viết lại bằng LLM (app)": generator.condense,
    }
    out = {}
    for name, make in modes.items():
        rows = []
        for item in items:
            query = make(item["question"], item["history"])
            got = store.query(expand_query(query), top_k=15)
            rank = next((i for i, c in enumerate(got, 1)
                         if any(chunk_matches(c, e) for e in item["expected"])), None)
            rows.append({"id": item["id"], "query": query, "rank": rank})
        n = len(rows)
        out[name] = {
            "recall_at_5": round(sum(r["rank"] is not None and r["rank"] <= 5 for r in rows) / n, 4),
            "recall_at_15": round(sum(r["rank"] is not None for r in rows) / n, 4),
            "mrr": round(sum(1 / r["rank"] for r in rows if r["rank"]) / n, 4),
            "per_question": rows,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--followup", action="store_true",
                    help="thêm thí nghiệm câu nối tiếp (gọi Groq ~7 lượt viết lại ngắn)")
    args = ap.parse_args()

    from evaluation.retrieval_dataset import COLLOQUIAL_QUESTIONS, RETRIEVAL_QUESTIONS
    from src.embeddings.embedder import Embedder
    from src.pipeline.rag import RAGPipeline, build_store
    from src.pipeline.relations import SUPERSEDED
    from src.vectorstore.store import VectorStore

    qs = RETRIEVAL_QUESTIONS + COLLOQUIAL_QUESTIONS
    emb = Embedder()
    full = build_store(emb)
    dropped = full._dropped_docs()

    t = time.perf_counter()
    bm25 = BM25Store(BM25Index(load_chunks(full)), dropped)
    print(f"dựng BM25: {time.perf_counter() - t:.0f}s")

    def pipe(store, **kw):
        return RAGPipeline(store=store, generator=None, **kw)

    components = [
        ("Đầy đủ (app)", pipe(full)),
        ("- từ điển thuật ngữ", pipe(full, expand_terms=False)),
        ("- tra theo số Điều", pipe(VectorStore(emb, article_lookup=False, superseded=SUPERSEDED))),
        ("- khử trùng", pipe(VectorStore(emb, article_lookup=True, superseded=SUPERSEDED,
                                         dedup=False))),
        ("BM25 thay dense (+ từ điển)", pipe(bm25)),
        ("Hybrid dense + BM25 (RRF)", pipe(HybridStore(full, bm25))),
    ]
    comp = [(name, _measure(p, qs)) for name, p in components]
    topk = [(f"top_k = {k}", _measure(pipe(full, top_k=k), qs)) for k in (5, 10, 15, 20)]
    for _, m in comp[1:] + topk:
        m["vs_full"] = compare_ranks(comp[0][1], m)

    print(f"\n## Thành phần ({len(qs)} câu, chấm phiên bản + Điều + đoạn bằng chứng)\n")
    print(_table(comp))
    print("\n## Số đoạn lấy về (cấu hình đầy đủ)\n")
    print(_table(topk))

    results = {"questions": len(qs), "components": dict(comp), "top_k": dict(topk)}
    if args.followup:
        from dotenv import load_dotenv
        from src.generation.generator import Generator
        load_dotenv()
        fu = followup_ablation(full, Generator())
        print("\n## Câu nối tiếp\n")
        print("| Cách tìm | R@5 | R@15 | MRR |\n|---|---|---|---|")
        for name, m in fu.items():
            print(f"| {name} | {m['recall_at_5']:.4f} | {m['recall_at_15']:.4f} | {m['mrr']:.4f} |")
        results["followup"] = fu
    elif RESULTS_PATH.exists():
        # Không chạy lại phần gọi Groq thì giữ kết quả lần trước, đừng xoá mất.
        old = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        if "followup" in old:
            results["followup"] = old["followup"]

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nđã ghi {RESULTS_PATH}")


if __name__ == "__main__":
    main()

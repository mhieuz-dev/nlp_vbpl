"""Nghiệm thu đầu-cuối: gọi đúng đường app chạy (retrieve + generate) và chấm ba việc.

- evidence: nguồn đúng có trong ngữ cảnh model được đọc (sau fit_to_context).
- behavior: làm đúng việc câu hỏi đòi - trả lời, hỏi lại, hay từ chối.
- grounded: trả lời đúng bằng chứng - hành vi đúng, trích [n] trỏ vào nguồn
  đúng, và có đủ chi tiết mấu chốt. Chỉ chấm cho câu answer/clarify.

Chạy: python -m evaluation.acceptance_eval [--split dev|holdout|all]
Gọi LLM thật (Groq free tier) nên chậm: hạn mức token/phút buộc phải chờ giữa
các câu. Không tốn tiền, NHƯNG dùng chung hạn mức 200.000 token/NGÀY với bản
deploy: mỗi câu ~5.300 token, một lượt 12 câu ~64.000. Ngày 29/09 chạy 2 lượt
dev + holdout là cạn hạn mức và web thật báo 429 khoảng nửa tiếng. Chạy tối đa
một lượt mỗi ngày, vào giờ ít người dùng.
"""
import argparse
import json
import re
import time

from evaluation.retrieval_eval import _norm, chunk_matches
from src.generation.generator import CLARIFY_PREFIX, GAP_PREFIX, is_rate_limited

_CITE_RE = re.compile(r"\[(\d+)\]")
METRICS = ("evidence", "behavior", "grounded")


def _is_right(chunk: dict, item: dict) -> bool:
    return any(chunk_matches(chunk, exp) for exp in item["expected"])


def score_item(item: dict, chunks: list[dict], result: dict) -> dict:
    """Chấm một câu. None = chỉ số không áp dụng cho loại câu này."""
    answer = result.get("answer", "")
    answered = result.get("answered", True)
    asks_back = CLARIFY_PREFIX in answer

    if item["kind"] == "abstain":
        # Từ chối hẳn, hoặc trả lời phần có căn cứ rồi ghi rõ phần chưa tìm thấy.
        behavior = (not answered) or GAP_PREFIX in answer
        return {"evidence": None, "behavior": behavior, "grounded": None}

    evidence = any(_is_right(c, item) for c in chunks)
    # Câu trả lời được: trả lời xong hỏi thêm cho sát trường hợp vẫn là đúng
    # (câu "báo trước bao nhiêu ngày" nêu đủ 45/30/3 ngày rồi hỏi loại hợp đồng).
    behavior = answered and asks_back if item["kind"] == "clarify" else answered

    cited = {int(n) for n in _CITE_RE.findall(answer)}
    cites_right = any(1 <= n <= len(chunks) and _is_right(chunks[n - 1], item)
                      for n in cited)
    text = _norm(answer)
    has_facts = all(any(_norm(v) in text for v in group) for group in item["must_contain"])
    return {"evidence": evidence, "behavior": behavior,
            "grounded": behavior and evidence and cites_right and has_facts}


def summarize(rows: list[dict]) -> dict:
    """Tỉ lệ theo tập dev/holdout/all; mẫu số chỉ gồm câu mà chỉ số áp dụng."""
    def rate(sub, m):
        vals = [r[m] for r in sub if r[m] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    out = {}
    for split in ("dev", "holdout", "all"):
        sub = [r for r in rows if split == "all" or r["split"] == split]
        if sub:
            out[split] = {"n": len(sub), **{m: rate(sub, m) for m in METRICS}}
    return out


def _retry_429(item, wait_s: int, call):
    """Gọi model, gặp giới hạn theo phút của Groq thì chờ rồi thử lại.

    Bọc cả retrieve: câu nối tiếp gọi model viết lại câu hỏi ngay trong đó.
    """
    for _ in range(5):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - chỉ nuốt 429, còn lại ném tiếp
            if not is_rate_limited(exc):
                raise
            print(f"    429, chờ {wait_s}s")
            time.sleep(wait_s)
    raise RuntimeError(f"{item['id']}: vẫn 429 sau 5 lần chờ")


def run(pipeline, items, pause_s: int = 20, wait_s: int = 60) -> list[dict]:
    rows = []
    for i, item in enumerate(items, start=1):
        chunks = _retry_429(item, wait_s,
                            lambda: pipeline.retrieve(item["question"], item.get("history")))
        result = _retry_429(item, wait_s, lambda: pipeline.generator.generate(
            item["question"], chunks, history=item.get("history")))
        s = score_item(item, chunks, result)
        rows.append({"id": item["id"], "split": item["split"], "kind": item["kind"],
                     **s, "query": getattr(pipeline, "last_query", None),
                     "answer": result.get("answer", "")})
        print(f"[{i}/{len(items)}] {item['split']:7} {item['kind']:7} {item['id']:28} "
              + " ".join(f"{m}={'-' if s[m] is None else int(s[m])}" for m in METRICS))
        # Groq free tier: ~8.000 token/phút, mỗi câu tốn ~6.000. Nghỉ để khỏi 429.
        if i < len(items):
            time.sleep(pause_s)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=("dev", "holdout", "all"), default="dev")
    ap.add_argument("--out", default="evaluation/acceptance_results.json",
                    help="ghi từng câu + tổng hợp (file sinh lại được, không commit)")
    ap.add_argument("--ids", default="",
                    help="chỉ chạy các id này (phẩy ngăn cách), để chạy tiếp khi Groq báo 429")
    args = ap.parse_args(argv)
    ids = {i.strip() for i in args.ids.split(",") if i.strip()}

    from dotenv import load_dotenv
    from src.embeddings.embedder import Embedder
    from src.generation.generator import Generator
    from src.ingestion.corpus_meta import read_meta
    from src.pipeline.rag import RAGPipeline, build_store
    from evaluation.acceptance_dataset import ACCEPTANCE

    load_dotenv()
    meta = read_meta()
    pipeline = RAGPipeline(store=build_store(Embedder()), generator=Generator(
        law_types=set(meta["law_types"]) if meta else None))
    items = [q for q in ACCEPTANCE if (args.split == "all" or q["split"] == args.split)
             and (not ids or q["id"] in ids)]
    rows = run(pipeline, items)
    summary = summarize(rows)

    print("\n| Tập | Số câu | Lấy đúng bằng chứng | Hành vi đúng | Trả lời đúng bằng chứng |")
    print("|---|---|---|---|---|")
    for split, m in summary.items():
        cells = ["-" if m[k] is None else f"{m[k]:.2f}" for k in METRICS]
        print(f"| {split} | {m['n']} | " + " | ".join(cells) + " |")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=1)
    print(f"\nđã ghi {args.out}")


if __name__ == "__main__":
    main()

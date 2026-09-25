"""Đo chất lượng TRUY XUẤT, không gọi mô hình sinh.

Khác với `evaluate_pipeline`: hàm đó gọi Gemini rồi kiểm từ khoá trong câu trả
lời, nên `avg_retrieval_score` vẫn cao khi hệ thống truy xuất sai một cách tự
tin. Ở đây mỗi câu hỏi có ground truth là (luật, số điều), nên đo được đúng
việc điều luật cần thiết có lọt vào top-k hay không, và ở hạng bao nhiêu.
"""
import re
import unicodedata

from src.generation.generator import fit_to_context


def _norm(text: str) -> str:
    """Bỏ dấu tiếng Việt và chữ số để so tên luật bất kể cách viết."""
    t = text.lower().replace("đ", "d")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\d+", " ", t)


def chunk_matches(chunk: dict, expected: tuple) -> bool:
    """Chunk có đúng là điều luật cần tìm không.

    `expected` là (khoá tên luật đã bỏ dấu, số điều). Khoá tên luật so bằng
    phép chứa vì cùng một bộ luật xuất hiện trong kho dưới nhiều cách viết:
    "Bộ Luật dân sự", "Bo Luat Dan Su", "Bo luat dan su 2015 296215".
    """
    law_key, article = expected
    if chunk.get("article") != article:
        return False
    return _norm(law_key).strip() in _norm(chunk.get("title", ""))


def evaluate_retrieval(pipeline, questions: list[dict], ks=(5, 10, 15)) -> dict:
    """Đo truy xuất qua đúng đường app chạy: pipeline.retrieve().

    Trước đây hàm này gọi thẳng store.query(), nên bỏ qua bước nối thuật ngữ
    luật mà app đang dùng - số đo không nói về app. Mỗi câu truy xuất MỘT lần
    với top_k của pipeline; Recall@k là "nguồn đúng nằm trong k hạng đầu của
    chính danh sách app nhận được".

    in_context: nguồn đúng còn sống sau fit_to_context (trần 16.000 ký tự),
    tức model thật sự được đọc nó. Lọt top-15 mà bị cắt thì model vẫn không thấy.
    """
    per_question = []
    for item in questions:
        raw = pipeline.retrieve(item["question"], fit=False)
        kept = fit_to_context(raw)
        rank = next((i for i, c in enumerate(raw, start=1)
                     if any(chunk_matches(c, exp) for exp in item["expected"])), None)
        per_question.append({
            "question": item["question"],
            "query": pipeline.search_query(item["question"]),
            "rank": rank,
            "in_context": rank is not None and rank <= len(kept),
            # Chunk đầu bảng dài quá trần bị cắt cụt chứ không bị bỏ: vẫn tính
            # là trong ngữ cảnh, nhưng đoạn chứa đáp án có thể đã rơi mất.
            "truncated": rank is not None and rank <= len(kept)
                         and len(kept[rank - 1]["text"]) < len(raw[rank - 1]["text"]),
        })

    n = len(questions)
    ranks = [q["rank"] for q in per_question]
    out = {"total_questions": n, "top_k": pipeline.top_k}
    for k in ks:
        out[f"recall_at_{k}"] = round(sum(r is not None and r <= k for r in ranks) / n, 4) if n else 0.0
    out["mrr"] = round(sum(1 / r for r in ranks if r) / n, 4) if n else 0.0
    out["in_context"] = round(sum(q["in_context"] for q in per_question) / n, 4) if n else 0.0
    out["per_question"] = per_question
    return out


def _bang(rows) -> str:
    cot = ["Bộ câu", "Từ điển", "R@5", "R@10", "R@15", "MRR@15", "Trong context"]
    dong = ["| " + " | ".join(cot) + " |", "|" + "---|" * len(cot)]
    for ten, bat, m in rows:
        dong.append(f"| {ten} ({m['total_questions']}) | {'bật' if bat else 'tắt'} | "
                    f"{m['recall_at_5']:.4f} | {m['recall_at_10']:.4f} | {m['recall_at_15']:.4f} | "
                    f"{m['mrr']:.4f} | {m['in_context']:.4f} |")
    return "\n".join(dong)


def main():
    """python -m evaluation.retrieval_eval - in bảng so sánh bật/tắt từ điển."""
    from src.embeddings.embedder import Embedder
    from src.pipeline.rag import RAGPipeline, build_store
    from evaluation.retrieval_dataset import RETRIEVAL_QUESTIONS, COLLOQUIAL_QUESTIONS

    store = build_store(Embedder())
    bo_cau = [("gốc", RETRIEVAL_QUESTIONS), ("đời thường", COLLOQUIAL_QUESTIONS),
              ("tất cả", RETRIEVAL_QUESTIONS + COLLOQUIAL_QUESTIONS)]
    rows, sai = [], []
    for bat in (False, True):
        # generator=None: câu đánh giá đều đứng một mình, không có lịch sử nên
        # không bao giờ tới bước viết lại câu nối tiếp.
        pipe = RAGPipeline(store=store, generator=None, expand_terms=bat)
        for ten, qs in bo_cau:
            m = evaluate_retrieval(pipe, qs)
            rows.append((ten, bat, m))
            if bat and ten == "tất cả":
                sai = [q for q in m["per_question"]
                       if q["rank"] is None or q["rank"] > 5 or not q["in_context"]]

    print(_bang(rows))
    print("\nCâu còn yếu khi bật từ điển (ngoài top-5 hoặc không vào được context):")
    for q in sai:
        hang = q["rank"] if q["rank"] else "ngoài top-15"
        print(f"- hạng {hang}, context {'có' if q['in_context'] else 'KHÔNG'}"
              f"{', bị cắt cụt' if q['truncated'] else ''}: {q['question']}")


if __name__ == "__main__":
    main()

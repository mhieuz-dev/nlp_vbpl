"""Đo chất lượng TRUY XUẤT, không gọi mô hình sinh.

Khác với `evaluate_pipeline`: hàm đó gọi Gemini rồi kiểm từ khoá trong câu trả
lời, nên `avg_retrieval_score` vẫn cao khi hệ thống truy xuất sai một cách tự
tin. Ở đây mỗi câu hỏi có ground truth là (luật, số điều), nên đo được đúng
việc điều luật cần thiết có lọt vào top-k hay không, và ở hạng bao nhiêu.
"""
import re
import unicodedata


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


def evaluate_retrieval(store, questions: list[dict], k: int = 5) -> dict:
    hits = 0
    reciprocal_ranks = 0.0

    for item in questions:
        results = store.query(item["question"], top_k=k)
        rank = None
        for i, chunk in enumerate(results, start=1):
            if any(chunk_matches(chunk, exp) for exp in item["expected"]):
                rank = i
                break
        if rank is not None:
            hits += 1
            reciprocal_ranks += 1 / rank

    n = len(questions)
    return {
        "k": k,
        "total_questions": n,
        "hits": hits,
        "recall_at_k": round(hits / n, 4) if n else 0.0,
        "mrr": round(reciprocal_ranks / n, 4) if n else 0.0,
    }

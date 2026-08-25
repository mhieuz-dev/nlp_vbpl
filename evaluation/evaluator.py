def evaluate_pipeline(pipeline, questions: list[dict]) -> dict:
    hits = 0
    total_score = 0.0

    for item in questions:
        result = pipeline.ask(item["question"])
        answer_lower = result["answer"].lower()
        keywords = item["expected_keywords"]

        hit = any(kw.lower() in answer_lower for kw in keywords)
        if hit:
            hits += 1

        scores = [c["score"] for c in result["retrieved_chunks"]]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        total_score += avg_score

    return {
        "hit_rate": hits / len(questions),
        "avg_retrieval_score": round(total_score / len(questions), 4),
        "total_questions": len(questions),
        "hits": hits,
    }

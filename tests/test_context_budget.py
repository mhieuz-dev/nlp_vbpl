from src.generation.generator import fit_to_context, MAX_CONTEXT_CHARS


def chunk(n, size):
    return {"chunk_id": f"c{n}", "article": n, "title": "Luật X",
            "law_type": "law", "score": 0.9 - n * 0.01, "text": "x" * size}


def test_keeps_all_chunks_when_under_budget():
    chunks = [chunk(i, 500) for i in range(5)]
    assert fit_to_context(chunks) == chunks


def test_drops_lowest_ranked_chunks_when_over_budget():
    # 10 chunk x 3000 ký tự = 30.000, vượt trần
    chunks = [chunk(i, 3000) for i in range(10)]
    kept = fit_to_context(chunks)
    assert len(kept) < 10
    assert sum(len(c["text"]) for c in kept) <= MAX_CONTEXT_CHARS
    # giữ đúng thứ tự xếp hạng, cắt từ dưới lên
    assert kept == chunks[:len(kept)]


def test_always_keeps_at_least_one_chunk():
    """Một điều luật dài hơn cả trần vẫn phải gửi, không thì không có gì để trả lời."""
    kept = fit_to_context([chunk(0, MAX_CONTEXT_CHARS * 2)])
    assert len(kept) == 1


def test_empty_input_gives_empty_output():
    assert fit_to_context([]) == []

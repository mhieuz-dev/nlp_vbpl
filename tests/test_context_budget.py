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


def test_oversize_first_chunk_is_truncated():
    """Điều dài hơn cả trần vẫn phải gửi, nhưng CẮT CỤT chứ không thả nguyên.

    Bug cũ: `if kept and ...` - vòng đầu kept còn rỗng nên chunk #1 luôn lọt
    qua nguyên vẹn. Kho thật có 35 chunk vượt 16.000 ký tự (dài nhất 116.731);
    chunk cỡ đó xếp hạng đầu là prompt ~33.000 token, Groq trả 413 Request
    too large (trần 8.000).
    """
    kept = fit_to_context([chunk(0, MAX_CONTEXT_CHARS * 2)])
    assert len(kept) == 1
    assert len(kept[0]["text"]) == MAX_CONTEXT_CHARS


def test_does_not_mutate_input_chunks():
    """Chunk gốc còn được dùng để hiện nguồn trên giao diện, không được sửa."""
    original = chunk(0, MAX_CONTEXT_CHARS * 2)
    fit_to_context([original])
    assert len(original["text"]) == MAX_CONTEXT_CHARS * 2


def test_empty_input_gives_empty_output():
    assert fit_to_context([]) == []

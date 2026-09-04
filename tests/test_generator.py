from unittest.mock import patch, MagicMock

import pytest

from src.generation.generator import Generator

SAMPLE_CHUNKS = [
    {"text": "Điều 1. Hợp đồng vô hiệu khi vi phạm điều kiện pháp luật.",
     "title": "Bộ luật Dân sự 2015", "law_type": "bo_luat", "score": 0.92},
]

FIVE_CHUNKS = [
    {"text": f"Điều {100+i}. Nội dung điều luật {i}.", "title": "Bộ luật Dân sự 2015",
     "law_type": "bo_luat", "score": 0.9 - i * 0.01}
    for i in range(5)
]


def _gen(answer_text):
    """Generator với client OpenAI-compatible đã mock. Trả (gen, mock_client, ctx)."""
    ctx = patch("src.generation.generator.OpenAI")
    mock_cls = ctx.start()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=answer_text))
    ]
    mock_cls.return_value = mock_client
    return Generator(api_key="fake_key"), mock_client, ctx


def _sent_messages(mock_client):
    return mock_client.chat.completions.create.call_args.kwargs["messages"]


def test_generate_returns_answer_and_sources():
    gen, _, ctx = _gen("Hợp đồng vô hiệu khi vi phạm quy định pháp luật.")
    try:
        result = gen.generate("Hợp đồng vô hiệu khi nào?", SAMPLE_CHUNKS)
        assert "answer" in result
        assert isinstance(result["sources"], list)
        assert "Bộ luật Dân sự 2015" in result["sources"]
    finally:
        ctx.stop()


def test_generate_extracts_citations_in_order_without_duplicates():
    gen, _, ctx = _gen("Câu một [1]. Câu hai [3]. Câu ba [1].")
    try:
        assert gen.generate("câu hỏi?", FIVE_CHUNKS)["citations"] == [1, 3]
    finally:
        ctx.stop()


def test_generate_filters_out_of_range_citations():
    gen, _, ctx = _gen("Bịa nguồn [9] và [0] nhưng [2] thì hợp lệ.")
    try:
        assert gen.generate("câu hỏi?", FIVE_CHUNKS)["citations"] == [2]
    finally:
        ctx.stop()


def test_prompt_numbers_the_chunks():
    gen, mock_client, ctx = _gen("Trả lời.")
    try:
        gen.generate("câu hỏi?", FIVE_CHUNKS)
        content = _sent_messages(mock_client)[-1]["content"]
        assert "[1]" in content and "[5]" in content
    finally:
        ctx.stop()


def test_generate_handles_empty_content():
    """Nội dung bị chặn -> message.content is None; không được để lọt 'None'."""
    gen, _, ctx = _gen(None)
    try:
        answer = gen.generate("câu hỏi hình sự?", FIVE_CHUNKS)["answer"]
        assert isinstance(answer, str) and answer.strip()
        assert answer not in ("None", "null")
    finally:
        ctx.stop()


def test_generate_asks_for_low_reasoning_effort():
    """Model suy nghĩ đốt nhiều token cho câu tra cứu có sẵn ngữ cảnh; xin mức thấp."""
    gen, mock_client, ctx = _gen("Trả lời [1].")
    try:
        gen.generate("câu hỏi?", FIVE_CHUNKS)
        assert mock_client.chat.completions.create.call_args.kwargs.get("reasoning_effort") == "low"
    finally:
        ctx.stop()


def test_generate_retries_without_reasoning_effort_if_provider_rejects_it():
    """Groq llama-3.3-70b không phải model suy nghĩ; gọi lại không kèm tham số đó."""
    ctx = patch("src.generation.generator.OpenAI")
    mock_cls = ctx.start()
    mock_client = MagicMock()
    calls = []

    def create(**kw):
        calls.append(kw)
        if "reasoning_effort" in kw:
            raise RuntimeError("400 reasoning_effort is not supported for this model")
        r = MagicMock()
        r.choices = [MagicMock(message=MagicMock(content="Trả lời [1]."))]
        return r

    mock_client.chat.completions.create.side_effect = create
    mock_cls.return_value = mock_client
    try:
        result = Generator(api_key="fake").generate("câu hỏi?", FIVE_CHUNKS)
        assert "Trả lời" in result["answer"]
        assert "reasoning_effort" not in calls[-1]
    finally:
        ctx.stop()


def test_generate_retries_on_503_then_succeeds():
    ctx = patch("src.generation.generator.OpenAI")
    mock_cls = ctx.start()
    mock_client = MagicMock()
    n = {"i": 0}

    def create(**kw):
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        r = MagicMock()
        r.choices = [MagicMock(message=MagicMock(content="Trả lời sau khi thử lại [1]."))]
        return r

    mock_client.chat.completions.create.side_effect = create
    mock_cls.return_value = mock_client
    with patch("src.generation.generator.RETRY_DELAYS", (0.0, 0.0)):
        try:
            result = Generator(api_key="fake").generate("câu hỏi?", FIVE_CHUNKS)
        finally:
            ctx.stop()
    assert n["i"] == 2
    assert "sau khi thử lại" in result["answer"]


def test_generate_gives_up_after_retries_exhausted():
    ctx = patch("src.generation.generator.OpenAI")
    mock_cls = ctx.start()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("503 UNAVAILABLE")
    mock_cls.return_value = mock_client
    with patch("src.generation.generator.RETRY_DELAYS", (0.0, 0.0)):
        try:
            with pytest.raises(RuntimeError):
                Generator(api_key="fake").generate("câu hỏi?", FIVE_CHUNKS)
        finally:
            ctx.stop()


def test_generator_reads_provider_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setenv("LLM_API_KEY", "groq_key")
    with patch("src.generation.generator.OpenAI") as mock_cls:
        gen = Generator()
        assert gen.model_name == "llama-3.3-70b-versatile"
        _, kwargs = mock_cls.call_args
        assert kwargs["base_url"] == "https://api.groq.com/openai/v1"
        assert kwargs["api_key"] == "groq_key"


def test_generate_strips_thinking_blocks():
    """qwen3.6 rò khối <think> tiếng Anh vào câu trả lời; không được để lọt ra UI."""
    gen, _, ctx = _gen(
        "<think>\nOkay the user asks about contracts. Let me check source [1].\n</think>\n"
        "Hợp đồng vô hiệu khi vi phạm điều kiện [1]."
    )
    try:
        answer = gen.generate("câu hỏi?", FIVE_CHUNKS)["answer"]
        assert "<think>" not in answer and "</think>" not in answer
        assert "Okay the user asks" not in answer
        assert answer.startswith("Hợp đồng vô hiệu")
    finally:
        ctx.stop()


def test_generate_strips_unclosed_thinking_block():
    """Bị cắt giữa chừng thì thẻ mở không có thẻ đóng - vẫn phải bỏ."""
    gen, _, ctx = _gen("<think>reasoning bị cắt ngang mà không đóng thẻ")
    try:
        answer = gen.generate("câu hỏi?", FIVE_CHUNKS)["answer"]
        assert "<think>" not in answer
        assert answer.strip()
    finally:
        ctx.stop()


def test_citations_ignore_numbers_inside_thinking_block():
    """Số nguồn model nhắc lúc suy nghĩ không được tính là trích dẫn thật."""
    gen, _, ctx = _gen("<think>maybe [4] or [5]?</think>Chỉ dùng nguồn [1].")
    try:
        assert gen.generate("câu hỏi?", FIVE_CHUNKS)["citations"] == [1]
    finally:
        ctx.stop()


def test_generate_flags_unanswerable_and_strips_marker():
    """Kho chỉ có luật/bộ luật/hiến pháp - hỏi mức phạt (nằm trong nghị định) thì
    phải nói không tìm thấy, không được ghép đại từ điều luật gần chủ đề."""
    gen, _, ctx = _gen(
        "KHÔNG_TÌM_THẤY\nCác điều luật được cung cấp không quy định mức phạt tiền "
        "cho hành vi vượt đèn đỏ. Mức phạt này nằm trong nghị định xử phạt vi phạm "
        "hành chính, không có trong kho."
    )
    try:
        r = gen.generate("Vượt đèn đỏ phạt bao nhiêu?", FIVE_CHUNKS)
        assert r["answered"] is False
        assert "KHÔNG_TÌM_THẤY" not in r["answer"]
        assert r["answer"].startswith("Các điều luật")
        assert r["citations"] == []
    finally:
        ctx.stop()


def test_generate_marks_normal_answer_as_answered():
    gen, _, ctx = _gen("Hợp đồng vô hiệu khi thiếu điều kiện [1].")
    try:
        r = gen.generate("câu hỏi?", FIVE_CHUNKS)
        assert r["answered"] is True
        assert r["citations"] == [1]
    finally:
        ctx.stop()


def test_prompt_tells_model_what_the_corpus_does_not_contain():
    """Model phải biết kho thiếu nghị định để giải thích ĐÚNG lý do không trả lời được."""
    gen, mock_client, ctx = _gen("Trả lời.")
    try:
        gen.generate("câu hỏi?", FIVE_CHUNKS)
        prompt = _sent_messages(mock_client)[-1]["content"]
        assert "nghị định" in prompt.lower()
        assert "KHÔNG_TÌM_THẤY" in prompt
    finally:
        ctx.stop()


def test_prompt_forbids_naming_document_numbers_not_in_corpus():
    """Model tự nêu \"Nghị định 123/2021/NĐ-CP\" - số hiệu lấy từ trí nhớ riêng,
    không có trong kho. Nêu sai số hiệu còn tệ hơn không nêu."""
    gen, mock_client, ctx = _gen("Trả lời.")
    try:
        gen.generate("câu hỏi?", FIVE_CHUNKS)
        prompt = _sent_messages(mock_client)[-1]["content"].lower()
        assert "số hiệu" in prompt
    finally:
        ctx.stop()

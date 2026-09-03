from unittest.mock import patch, MagicMock
from src.generation.generator import Generator

SAMPLE_CHUNKS = [
    {"text": "Điều 1. Hợp đồng vô hiệu khi vi phạm điều kiện pháp luật.", "title": "Bộ luật Dân sự 2015", "law_type": "bo_luat", "score": 0.92},
]

def test_generate_returns_answer_and_sources():
    with patch("src.generation.generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = "Hợp đồng vô hiệu khi vi phạm quy định pháp luật."
        mock_genai.Client.return_value = mock_client
        gen = Generator(api_key="fake_key")
        result = gen.generate("Hợp đồng vô hiệu khi nào?", SAMPLE_CHUNKS)
        assert "answer" in result
        assert "sources" in result
        assert isinstance(result["sources"], list)

def test_generate_includes_source_titles():
    with patch("src.generation.generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = "Câu trả lời."
        mock_genai.Client.return_value = mock_client
        gen = Generator(api_key="fake_key")
        result = gen.generate("câu hỏi?", SAMPLE_CHUNKS)
        assert "Bộ luật Dân sự 2015" in result["sources"]


FIVE_CHUNKS = [
    {"text": f"Điều {100+i}. Nội dung điều luật {i}.", "title": "Bộ luật Dân sự 2015",
     "law_type": "bo_luat", "score": 0.9 - i * 0.01}
    for i in range(5)
]


def _gen_with_answer(answer_text):
    from unittest.mock import patch, MagicMock
    ctx = patch("src.generation.generator.genai")
    mock_genai = ctx.start()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = answer_text
    mock_genai.Client.return_value = mock_client
    return Generator(api_key="fake_key"), mock_client, ctx


def test_generate_extracts_citations():
    gen, _, ctx = _gen_with_answer("Câu một [1]. Câu hai [3]. Câu ba [1].")
    try:
        result = gen.generate("câu hỏi?", FIVE_CHUNKS)
        assert result["citations"] == [1, 3]
    finally:
        ctx.stop()


def test_generate_filters_out_of_range_citations():
    gen, _, ctx = _gen_with_answer("Bịa nguồn [9] và [0] nhưng [2] thì hợp lệ.")
    try:
        result = gen.generate("câu hỏi?", FIVE_CHUNKS)
        assert result["citations"] == [2]
    finally:
        ctx.stop()


def test_prompt_numbers_the_chunks():
    gen, mock_client, ctx = _gen_with_answer("Trả lời.")
    try:
        gen.generate("câu hỏi?", FIVE_CHUNKS)
        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "[1]" in prompt
        assert "[5]" in prompt
    finally:
        ctx.stop()


def test_generate_handles_blocked_response():
    """Gemini trả response.text = None khi câu trả lời bị chặn — không được để lọt 'None'."""
    gen, _, ctx = _gen_with_answer(None)
    try:
        result = gen.generate("câu hỏi hình sự?", FIVE_CHUNKS)
        assert isinstance(result["answer"], str)
        assert result["answer"].strip()
        assert result["answer"] not in ("None", "null")
    finally:
        ctx.stop()


def test_generate_caps_thinking_budget():
    """Model mặc định đốt ~1400 token suy nghĩ cho một câu tra cứu; phải giới hạn lại."""
    gen, mock_client, ctx = _gen_with_answer("Trả lời [1].")
    try:
        gen.generate("câu hỏi?", FIVE_CHUNKS)
        cfg = mock_client.models.generate_content.call_args.kwargs.get("config")
        assert cfg is not None, "phải truyền config"
        budget = cfg.thinking_config.thinking_budget
        assert 0 < budget <= 256, f"budget phải nhỏ và dương, đang là {budget}"
    finally:
        ctx.stop()


def test_generate_retries_on_503_then_succeeds():
    """Gemini hay trả 503 'high demand'; retry thay vì ném lỗi ra người dùng."""
    from unittest.mock import patch, MagicMock
    import src.generation.generator as G

    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        r = MagicMock()
        r.text = "Trả lời sau khi thử lại [1]."
        return r

    with patch.object(G, "genai") as mock_genai, \
         patch.object(G, "RETRY_DELAYS", (0.0, 0.0)):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = flaky
        mock_genai.Client.return_value = mock_client
        gen = G.Generator(api_key="fake_key")
        result = gen.generate("câu hỏi?", FIVE_CHUNKS)

    assert calls["n"] == 2, "phải thử lại đúng một lần"
    assert "sau khi thử lại" in result["answer"]


def test_generate_gives_up_after_retries_exhausted():
    from unittest.mock import patch, MagicMock
    import pytest as _pytest
    import src.generation.generator as G

    with patch.object(G, "genai") as mock_genai, \
         patch.object(G, "RETRY_DELAYS", (0.0, 0.0)):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("503 UNAVAILABLE")
        mock_genai.Client.return_value = mock_client
        gen = G.Generator(api_key="fake_key")
        with _pytest.raises(RuntimeError):
            gen.generate("câu hỏi?", FIVE_CHUNKS)

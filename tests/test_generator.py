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

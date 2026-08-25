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

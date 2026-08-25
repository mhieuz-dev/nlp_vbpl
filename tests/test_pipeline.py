from unittest.mock import MagicMock
from src.pipeline.rag import RAGPipeline

def test_pipeline_ask_returns_answer():
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"text": "Điều 1.", "title": "Luật test", "law_type": "luat", "score": 0.9}
    ]
    mock_generator = MagicMock()
    mock_generator.generate.return_value = {
        "answer": "Câu trả lời",
        "sources": ["Luật test"],
        "chunks_used": [],
    }
    pipeline = RAGPipeline(store=mock_store, generator=mock_generator)
    result = pipeline.ask("Hỏi gì đó?")
    assert "answer" in result
    assert "sources" in result
    assert "retrieved_chunks" in result
    mock_store.query.assert_called_once_with("Hỏi gì đó?", top_k=5)

def test_pipeline_passes_chunks_to_generator():
    mock_store = MagicMock()
    chunks = [{"text": "chunk", "title": "T", "law_type": "luat", "score": 0.8}]
    mock_store.query.return_value = chunks
    mock_generator = MagicMock()
    mock_generator.generate.return_value = {"answer": "A", "sources": [], "chunks_used": chunks}
    pipeline = RAGPipeline(store=mock_store, generator=mock_generator)
    pipeline.ask("câu hỏi")
    mock_generator.generate.assert_called_once_with("câu hỏi", chunks)

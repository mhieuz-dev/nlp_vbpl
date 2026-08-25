from unittest.mock import MagicMock
from evaluation.evaluator import evaluate_pipeline

def test_evaluate_returns_metrics():
    mock_pipeline = MagicMock()
    mock_pipeline.ask.return_value = {
        "answer": "hợp đồng vi phạm điều kiện thì vô hiệu",
        "sources": ["Bộ luật Dân sự"],
        "retrieved_chunks": [{"score": 0.85, "text": "...", "title": "...", "law_type": "..."}],
    }
    questions = [{"question": "Hợp đồng vô hiệu khi nào?", "expected_keywords": ["vi phạm", "vô hiệu"]}]
    metrics = evaluate_pipeline(mock_pipeline, questions)
    assert "hit_rate" in metrics
    assert "avg_retrieval_score" in metrics
    assert 0.0 <= metrics["hit_rate"] <= 1.0

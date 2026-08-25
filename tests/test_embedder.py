from src.embeddings.embedder import Embedder

def test_embedder_returns_vectors():
    embedder = Embedder()
    texts = ["Điều 1. Phạm vi điều chỉnh", "Hợp đồng vô hiệu khi nào?"]
    vectors = embedder.embed(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 768

def test_embedder_single_text():
    embedder = Embedder()
    vectors = embedder.embed(["test"])
    assert len(vectors) == 1

def test_embedder_consistent_dimension():
    embedder = Embedder()
    v1 = embedder.embed(["văn bản ngắn"])
    v2 = embedder.embed(["đây là một văn bản pháp luật rất dài hơn nhiều"])
    assert len(v1[0]) == len(v2[0])

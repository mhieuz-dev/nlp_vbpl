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
    # Kiểm hành vi (truyền đúng top_k đã cấu hình), không ghim con số mặc định.
    mock_store.query.assert_called_once_with("Hỏi gì đó?", top_k=pipeline.top_k)


def test_pipeline_honours_custom_top_k():
    mock_store = MagicMock()
    mock_store.query.return_value = []
    mock_generator = MagicMock()
    mock_generator.generate.return_value = {"answer": "A", "sources": [], "chunks_used": []}
    RAGPipeline(store=mock_store, generator=mock_generator, top_k=3).ask("q")
    mock_store.query.assert_called_once_with("q", top_k=3)

def test_pipeline_passes_chunks_to_generator():
    mock_store = MagicMock()
    chunks = [{"text": "chunk", "title": "T", "law_type": "luat", "score": 0.8}]
    mock_store.query.return_value = chunks
    mock_generator = MagicMock()
    mock_generator.generate.return_value = {"answer": "A", "sources": [], "chunks_used": chunks}
    pipeline = RAGPipeline(store=mock_store, generator=mock_generator)
    pipeline.ask("câu hỏi")
    mock_generator.generate.assert_called_once_with("câu hỏi", chunks, history=None)


def _pipeline(chunks=None, **kw):
    store = MagicMock()
    store.query.return_value = chunks or []
    generator = MagicMock(spec=["generate"])   # không có condense: lui về ghép chuỗi
    generator.generate.return_value = {"answer": "A", "sources": []}
    return RAGPipeline(store=store, generator=generator, **kw), store


def test_retrieve_noi_thuat_ngu_luat_mac_dinh():
    pipe, store = _pipeline()
    pipe.retrieve("Ô tô vượt đèn đỏ phạt bao nhiêu?")
    q = store.query.call_args.args[0]
    assert "không chấp hành hiệu lệnh của đèn tín hiệu giao thông" in q


def test_retrieve_tat_tu_dien_thi_truy_van_giu_nguyen():
    """Cờ này để bộ đánh giá đo được từ điển giúp bao nhiêu."""
    pipe, store = _pipeline(expand_terms=False)
    pipe.retrieve("Ô tô vượt đèn đỏ phạt bao nhiêu?")
    assert store.query.call_args.args[0] == "Ô tô vượt đèn đỏ phạt bao nhiêu?"


def test_retrieve_cat_theo_tran_ngu_canh_tru_khi_fit_false():
    to = [{"text": "x" * 9000, "title": "T", "law_type": "luat", "score": 0.9}] * 3
    pipe, _ = _pipeline(chunks=to)
    assert len(pipe.retrieve("q")) < 3
    assert len(pipe.retrieve("q", fit=False)) == 3


def test_ask_dung_chung_duong_truy_xuat_voi_server():
    """Trước đây ask() bỏ qua câu nối tiếp, từ điển và trần ngữ cảnh."""
    pipe, store = _pipeline()
    lich_su = [{"role": "user", "content": "Xe máy vượt đèn đỏ phạt bao nhiêu?"}]
    pipe.ask("còn ô tô thì sao?", history=lich_su)
    q = store.query.call_args.args[0]
    assert q.startswith("Xe máy vượt đèn đỏ phạt bao nhiêu? còn ô tô thì sao?")
    assert "đèn tín hiệu giao thông" in q
    pipe.generator.generate.assert_called_once_with("còn ô tô thì sao?", [], history=lich_su)

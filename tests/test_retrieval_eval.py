from evaluation.retrieval_eval import chunk_matches, evaluate_retrieval
from src.pipeline.rag import RAGPipeline

BLDS = frozenset({"91/2015/QH13", "bo-luat-dan-su"})
ND168 = frozenset({"congbao-43733"})


def chunk(doc_id, article, text=""):
    return {"doc_id": doc_id, "title": doc_id, "article": article, "score": 0.9,
            "text": text, "chunk_id": "x"}


class FakeStore:
    """Trả về đúng danh sách đã dựng sẵn cho mỗi câu hỏi."""

    def __init__(self, by_question):
        self._by_question = by_question

    def query(self, question, top_k=5):
        self.seen = question
        return self._by_question[question][:top_k]


def pipe(by_question, expand_terms=False):
    return RAGPipeline(store=FakeStore(by_question), generator=None, expand_terms=expand_terms)


def test_chunk_matches_moi_ban_sao_trong_tap_doc_id():
    for doc_id in BLDS:
        assert chunk_matches(chunk(doc_id, 407), (BLDS, 407)) is True


def test_chunk_matches_tu_choi_luat_sua_doi_cung_so_dieu():
    """Khoá tên cũ bỏ chữ số nên luật sửa đổi BLHS 12/2017 cũng được tính là trúng."""
    blhs = frozenset({"100/2015/QH13"})
    assert chunk_matches(chunk("12/2017/QH14", 9), (blhs, 9)) is False


def test_chunk_matches_rejects_wrong_article_number():
    assert chunk_matches(chunk("91/2015/QH13", 408), (BLDS, 407)) is False


def test_chunk_matches_doi_dung_doan_bang_chung():
    """Điều 6 NĐ 168 bị chia 18 mảnh: đúng Điều mà sai khoản thì không có đáp án."""
    exp = (ND168, 6, ("18.000.000 đồng đến 20.000.000 đồng",
                      "không chấp hành hiệu lệnh của đèn tín hiệu giao thông"))
    khoan_9 = chunk("congbao-43733", 6, "Điều 6.\n9. Phạt tiền từ 18.000.000 đồng đến "
                    "20.000.000 đồng ...\nb) Không chấp hành hiệu lệnh của đèn tín hiệu giao thông;")
    khoan_2 = chunk("congbao-43733", 6, "Điều 6.\n2. Phạt tiền từ 400.000 đồng đến 600.000 đồng")
    assert chunk_matches(khoan_9, exp) is True
    assert chunk_matches(khoan_2, exp) is False
    assert chunk_matches(khoan_2, exp, evidence=False) is True


def test_recall_counts_hit_only_when_expected_article_in_topk():
    q = "Hợp đồng vô hiệu khi nào?"
    p = pipe({q: [chunk("luat-bao-hiem", 22), chunk("bo-luat-lao-dong", 49),
                  chunk("91/2015/QH13", 407)]})
    m = evaluate_retrieval(p, [{"question": q, "expected": [(BLDS, 407)]}], ks=(2, 3))
    assert m["recall_at_3"] == 1.0
    assert m["recall_at_2"] == 0.0


def test_mrr_uses_rank_of_first_correct_article():
    q = "Hợp đồng vô hiệu khi nào?"
    p = pipe({q: [chunk("luat-bao-hiem", 22), chunk("bo-luat-lao-dong", 49),
                  chunk("91/2015/QH13", 407)]})
    m = evaluate_retrieval(p, [{"question": q, "expected": [(BLDS, 407)]}])
    assert m["mrr"] == round(1 / 3, 4), m["mrr"]
    assert m["per_question"][0]["rank"] == 3


def test_mrr_is_zero_when_nothing_correct_retrieved():
    q = "câu hỏi lạc đề"
    p = pipe({q: [chunk("luat-nha-o", 1)]})
    m = evaluate_retrieval(p, [{"question": q, "expected": [(BLDS, 407)]}])
    assert m["mrr"] == 0.0 and m["recall_at_5"] == 0.0
    assert m["per_question"][0]["rank"] is None


def test_eval_di_qua_tu_dien_thuat_ngu_giong_app():
    """Trước đây eval gọi thẳng store.query nên không đo được từ điển."""
    q = "Ô tô vượt đèn đỏ phạt bao nhiêu?"
    p = pipe({}, expand_terms=True)
    p.store._by_question = {p.search_query(q): [chunk("luat-nha-o", 1)]}
    evaluate_retrieval(p, [{"question": q, "expected": [(BLDS, 407)]}])
    assert "đèn tín hiệu giao thông" in p.store.seen


def test_nguon_dung_bi_cat_khoi_context_thi_khong_tinh_in_context():
    """Lọt top-k nhưng rơi ngoài trần 16.000 ký tự thì model không đọc được."""
    q = "q"
    p = pipe({q: [chunk("luat-nha-o", 1, "x" * 9000), chunk("luat-nha-o", 2, "x" * 9000),
                  chunk("91/2015/QH13", 407, "đáp án")]})
    m = evaluate_retrieval(p, [{"question": q, "expected": [(BLDS, 407)]}])
    assert m["recall_at_5"] == 1.0
    assert m["in_context"] == 0.0


def test_chunk_dau_bi_cat_cut_mat_doan_bang_chung_thi_khong_tinh_in_context():
    """fit_to_context cắt cụt chunk đầu dài quá trần; đáp án ở đuôi thì rơi mất."""
    q = "q"
    dai = "Điều 6. " + "x" * 17000 + " 18.000.000 đồng đến 20.000.000 đồng"
    p = pipe({q: [chunk("congbao-43733", 6, dai)]})
    exp = (ND168, 6, ("18.000.000 đồng đến 20.000.000 đồng",))
    m = evaluate_retrieval(p, [{"question": q, "expected": [exp]}])
    assert m["per_question"][0]["rank"] == 1
    assert m["in_context"] == 0.0

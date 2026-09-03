from evaluation.retrieval_eval import chunk_matches, evaluate_retrieval


def chunk(title, article):
    return {"title": title, "article": article, "score": 0.9, "text": "", "chunk_id": "x"}


class FakeStore:
    """Trả về đúng danh sách đã dựng sẵn cho mỗi câu hỏi."""

    def __init__(self, by_question):
        self._by_question = by_question

    def query(self, question, top_k=5):
        return self._by_question[question][:top_k]


def test_chunk_matches_ignores_title_spelling_variants():
    # Cùng một bộ luật trong kho có 3 cách viết tên khác nhau.
    for title in ["Bộ Luật dân sự", "Bo Luat Dan Su", "Bo luat dan su 2015 296215"]:
        assert chunk_matches(chunk(title, 407), ("dan su", 407)) is True


def test_chunk_matches_rejects_same_article_in_wrong_law():
    assert chunk_matches(chunk("Bộ luật Tố tụng dân sự", 122), ("bo luat dan su", 122)) is False


def test_chunk_matches_rejects_wrong_article_number():
    assert chunk_matches(chunk("Bộ Luật dân sự", 408), ("dan su", 407)) is False


def test_recall_counts_hit_only_when_expected_article_in_topk():
    q = "Hợp đồng vô hiệu khi nào?"
    store = FakeStore({q: [chunk("Luật Kinh doanh bảo hiểm", 22),
                           chunk("Bộ luật Lao động", 49),
                           chunk("Bộ Luật dân sự", 407)]})
    ds = [{"question": q, "expected": [("dan su", 407)]}]
    assert evaluate_retrieval(store, ds, k=3)["recall_at_k"] == 1.0
    assert evaluate_retrieval(store, ds, k=2)["recall_at_k"] == 0.0


def test_mrr_uses_rank_of_first_correct_article():
    q = "Hợp đồng vô hiệu khi nào?"
    store = FakeStore({q: [chunk("Luật Kinh doanh bảo hiểm", 22),
                           chunk("Bộ luật Lao động", 49),
                           chunk("Bộ Luật dân sự", 407)]})
    ds = [{"question": q, "expected": [("dan su", 407)]}]
    m = evaluate_retrieval(store, ds, k=5)
    assert m["mrr"] == round(1 / 3, 4), m["mrr"]


def test_mrr_is_zero_when_nothing_correct_retrieved():
    q = "câu hỏi lạc đề"
    store = FakeStore({q: [chunk("Luật Nhà ở", 1)]})
    ds = [{"question": q, "expected": [("dan su", 407)]}]
    m = evaluate_retrieval(store, ds, k=5)
    assert m["mrr"] == 0.0 and m["recall_at_k"] == 0.0


def test_chunk_matches_handles_d_with_stroke():
    """`đ` không phải ký tự có dấu tổ hợp nên NFD không tách nó thành `d`.

    Bỏ sót chuyện này làm mọi luật có chữ `đ` trong tên (Hôn nhân và gia đình)
    không bao giờ khớp, khiến eval báo trượt trong khi truy xuất đúng.
    """
    for title in ["Luật Hôn nhân và gia đình", "Luat Hon nhan va gia dinh 2014 238640"]:
        assert chunk_matches(chunk(title, 8), ("luat hon nhan va gia dinh", 8)) is True

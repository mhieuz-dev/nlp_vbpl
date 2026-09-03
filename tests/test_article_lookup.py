from src.vectorstore.article_index import parse_article_ref, ArticleIndex


def test_parse_finds_article_number_and_law():
    assert parse_article_ref("Điều 117 Bộ luật Dân sự quy định gì?") == (117, "bo luat dan su")
    assert parse_article_ref("Nội dung Điều 9 Bộ luật Hình sự là gì?") == (9, "bo luat hinh su")


def test_parse_finds_article_without_law():
    assert parse_article_ref("Điều 630 nói về vấn đề gì?") == (630, None)


def test_parse_returns_none_when_no_article_named():
    assert parse_article_ref("Hợp đồng vô hiệu khi nào?") is None
    assert parse_article_ref("Tuổi kết hôn tối thiểu?") is None


def test_parse_ignores_number_not_attached_to_dieu():
    assert parse_article_ref("Bao nhiêu tuổi thì chịu trách nhiệm hình sự 18?") is None


class FakeCollection:
    """Đủ để dựng index: trả về id, document, metadata theo trang."""

    def __init__(self, rows):
        self._rows = rows

    def count(self):
        return len(self._rows)

    def get(self, include=None, limit=None, offset=0):
        page = self._rows[offset:offset + limit]
        return {
            "ids": [r[0] for r in page],
            "documents": [r[1] for r in page],
            "metadatas": [{"title": r[2]} for r in page],
        }


ROWS = [
    ("d_0", "Điều 117. Điều kiện có hiệu lực của giao dịch dân sự...", "Bộ Luật dân sự"),
    ("d_1", "Điều 117. Điều kiện có hiệu lực của giao dịch dân sự...", "Bo Luat Dan Su"),
    ("t_0", "Điều 117. Buộc thực hiện trước nghĩa vụ bồi thường...", "Bộ luật Tố tụng dân sự"),
    ("h_0", "Điều 9. Phân loại tội phạm...", "Bộ luật Hình sự"),
    ("x_0", "Chương I. Quy định chung.", "Luật Nhà ở"),
]


def test_index_finds_article_in_the_named_law_only():
    idx = ArticleIndex(FakeCollection(ROWS))
    assert set(idx.find(117, "bo luat dan su")) == {"d_0", "d_1"}


def test_index_without_law_hint_returns_every_law_with_that_article():
    idx = ArticleIndex(FakeCollection(ROWS))
    assert set(idx.find(117, None)) == {"d_0", "d_1", "t_0"}


def test_index_returns_empty_for_unknown_article():
    idx = ArticleIndex(FakeCollection(ROWS))
    assert idx.find(999, None) == []


def test_index_skips_chunks_without_dieu_header():
    idx = ArticleIndex(FakeCollection(ROWS))
    assert "x_0" not in idx.find(1, None)

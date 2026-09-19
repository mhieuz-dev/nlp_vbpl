"""Nối thuật ngữ pháp lý vào truy vấn đời thường."""
from src.pipeline.synonyms import expand_query, MAX_THEM


def test_noi_them_thuat_ngu_luat_cho_cach_noi_doi_thuong():
    q = "Ô tô vượt đèn đỏ bị phạt bao nhiêu tiền?"
    ra = expand_query(q)
    assert ra.startswith(q)          # câu gốc giữ NGUYÊN, chỉ nối thêm
    assert "không chấp hành hiệu lệnh của đèn tín hiệu giao thông" in ra


def test_giu_nguyen_khi_cau_hoi_da_dung_tu_ngu_luat():
    """Đây là lý do bộ 22 câu cũ không suy giảm: chúng không chạm từ điển."""
    q = "Thời hiệu khởi kiện tranh chấp hợp đồng dân sự là bao lâu?"
    assert expand_query(q) == q


def test_khong_noi_lai_thuat_ngu_da_co_san_trong_cau_hoi():
    q = "Người lái xe trong máu hoặc hơi thở có nồng độ cồn bị phạt thế nào khi nhậu?"
    assert expand_query(q).count("trong máu hoặc hơi thở có nồng độ cồn") == 1


def test_chan_tran_so_thuat_ngu_noi_them():
    """Chạm nhiều mục thì phần thêm vào dài hơn cả câu hỏi và át mất chủ đề -
    đúng lỗi đã gặp khi ghép nguyên câu hỏi trước vào câu nối tiếp."""
    q = "ăn trộm rồi đánh người, lừa tiền, trốn thuế, nhậu, tăng ca, mất cọc"
    them = expand_query(q)[len(q):]
    assert 0 < them.count("tội") + them.count("tiền lương") <= MAX_THEM


def test_khong_phan_biet_hoa_thuong():
    assert expand_query("VƯỢT ĐÈN ĐỎ phạt bao nhiêu?") != "VƯỢT ĐÈN ĐỎ phạt bao nhiêu?"

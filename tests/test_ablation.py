"""Phần thuần của thí nghiệm cắt bỏ: không nạp mô hình, không chạm kho thật."""
from evaluation.ablation import BM25Index, dedup_top, rrf_merge, tokenize


def _c(cid, text, doc="d", article=None, issue_date=""):
    return {"chunk_id": cid, "doc_id": doc, "text": text, "article": article,
            "issue_date": issue_date}


CHUNKS = [
    _c("a", "Điều 6. Phạt tiền người điều khiển xe ô tô không chấp hành hiệu lệnh đèn tín hiệu"),
    _c("b", "Điều 8. Tuổi kết hôn: nam từ đủ 20 tuổi, nữ từ đủ 18 tuổi"),
    _c("c", "Điều 173. Tội trộm cắp tài sản"),
]


def test_tokenize_giu_dau_va_chu_so():
    assert tokenize("Phạt 18.000.000 đồng, Điều 6") == ["phạt", "18", "000", "000", "đồng", "điều", "6"]


def test_bm25_xep_doan_trung_tu_khoa_len_dau():
    idx = BM25Index(CHUNKS)
    assert [c["chunk_id"] for c in idx.search("tuổi kết hôn của nữ", 3)][0] == "b"
    assert idx.search("xyz qwerty", 3) == []


def test_rrf_cong_diem_theo_hang_cua_hai_danh_sach():
    a, b, c = CHUNKS
    # b đứng hạng 2 ở cả hai danh sách nên vượt a (hạng 1 ở một danh sách duy nhất).
    merged = rrf_merge([[a, b], [c, b]], k=1)
    assert [x["chunk_id"] for x in merged] == ["b", "a", "c"]


def test_dedup_top_gop_ban_sao_giu_ban_moi_hon():
    cu = _c("cu", "Điều 6. Nội dung y hệt", doc="cu", issue_date="2019-12-30")
    moi = _c("moi", "Điều 6. Nội dung y hệt", doc="moi", issue_date="2024-12-26")
    khac = _c("khac", "Điều 7. Nội dung khác hẳn")
    got = dedup_top([cu, khac, moi], top_k=5)
    assert [x["chunk_id"] for x in got] == ["moi", "khac"]


def test_rrf_cong_don_hai_ban_sao_cua_cung_mot_dieu():
    """Dense lấy bản sao này, BM25 lấy bản sao kia của cùng một điều: vẫn phải cộng dồn."""
    ban1 = _c("blds_1", "Điều 117. Điều kiện có hiệu lực của giao dịch dân sự", doc="91/2015/QH13")
    ban2 = _c("blds_2", "Điều 117. Điều kiện có hiệu lực của giao dịch dân sự", doc="bo-luat-dan-su")
    a, b, _ = CHUNKS
    merged = rrf_merge([[a, ban1], [b, ban2]], k=1)
    assert [x["chunk_id"] for x in merged][0] in ("blds_1", "blds_2")
    assert len(merged) == 3


def test_compare_ranks_dem_cau_tot_len_xau_di():
    from evaluation.ablation import compare_ranks
    base = {"per_question": [{"rank": 1}, {"rank": 5}, {"rank": None}, {"rank": 2}]}
    other = {"per_question": [{"rank": 1}, {"rank": 2}, {"rank": 9}, {"rank": None}]}
    assert compare_ranks(base, other) == {"better": 2, "worse": 1}

"""Câu hỏi nối tiếp: nhận diện, ghép truy vấn, bóc số dẫn nguồn."""
from src.pipeline.followup import is_followup, retrieval_query, strip_citations

LICH_SU = [
    {"role": "user", "content": "Vượt đèn đỏ bị phạt bao nhiêu tiền?"},
    {"role": "assistant", "content": "Xe mô tô 4.000.000 đến 6.000.000 đồng [3]"},
]


def test_cau_dung_mot_minh_khong_bi_coi_la_noi_tiep():
    assert not is_followup(
        "Tuổi kết hôn tối thiểu theo Luật Hôn nhân và Gia đình là bao nhiêu?")


def test_cau_cut_va_cau_co_tu_noi_deu_la_noi_tiep():
    assert is_followup("còn ô tô thì sao?")
    assert is_followup("vậy nếu người đó chưa đủ 18 tuổi thì mức phạt thế nào")


def test_khong_co_lich_su_thi_giu_nguyen_cau_hoi():
    """Đường đi của mọi câu đầu tiên, và của toàn bộ bộ đánh giá Recall.

    Nếu chỗ này đổi câu hỏi thì số Recall@5 0,864 đo trước đây không còn nói
    lên điều gì nữa.
    """
    q = "còn ô tô thì sao?"
    assert retrieval_query(q, []) == q
    assert retrieval_query(q, None) == q


def test_cau_noi_tiep_duoc_ghep_them_cau_hoi_truoc():
    assert retrieval_query("còn ô tô thì sao?", LICH_SU) == (
        "Vượt đèn đỏ bị phạt bao nhiêu tiền? còn ô tô thì sao?")


def test_cau_dung_mot_minh_khong_bi_ghep_du_co_lich_su():
    q = "Thời hiệu khởi kiện tranh chấp hợp đồng dân sự là bao lâu?"
    assert retrieval_query(q, LICH_SU) == q


def test_chi_ghep_cau_hoi_cua_nguoi_dung_chu_khong_ghep_cau_tra_loi():
    """Câu trả lời dài gấp nhiều lần câu hỏi; gộp vào là nó át mất chủ đề."""
    assert "4.000.000" not in retrieval_query("còn ô tô thì sao?", LICH_SU)


def test_boc_so_dan_nguon_khoi_cau_tra_loi_cu():
    assert strip_citations("Xe máy 4-6 triệu [3] và ô tô [8]") == (
        "Xe máy 4-6 triệu  và ô tô ")


# ---------- viết lại câu hỏi nối tiếp ----------

def test_dung_cau_viet_lai_khi_co_ham_viet_lai():
    viet_lai = lambda q, h: "Ô tô vượt đèn đỏ bị phạt bao nhiêu tiền?"
    assert retrieval_query("còn ô tô thì sao?", LICH_SU, condense=viet_lai) == (
        "Ô tô vượt đèn đỏ bị phạt bao nhiêu tiền?")


def test_khong_goi_ham_viet_lai_cho_cau_tu_dung_duoc():
    """Câu đã đủ nghĩa mà đem viết lại là làm hỏng: đo trước đây Recall@5 tụt
    từ 0,864 xuống 0,545 vì model thêm chữ thừa, loãng mất từ khoá pháp lý."""
    da_goi = []
    def viet_lai(q, h):
        da_goi.append(q)
        return "câu khác hẳn"
    q = "Thời hiệu khởi kiện tranh chấp hợp đồng dân sự là bao lâu?"
    assert retrieval_query(q, LICH_SU, condense=viet_lai) == q
    assert da_goi == []


def test_viet_lai_hong_thi_lui_ve_ghep_chuoi():
    def no(q, h):
        raise RuntimeError("mạng hỏng")
    assert retrieval_query("còn ô tô thì sao?", LICH_SU, condense=no) == (
        "Vượt đèn đỏ bị phạt bao nhiêu tiền? còn ô tô thì sao?")


def test_viet_lai_tra_ve_rong_hoac_le_thi_lui_ve_ghep_chuoi():
    ghep = "Vượt đèn đỏ bị phạt bao nhiêu tiền? còn ô tô thì sao?"
    assert retrieval_query("còn ô tô thì sao?", LICH_SU, condense=lambda q, h: "") == ghep
    # Dài bất thường nghĩa là model kể lể thay vì viết một câu hỏi.
    assert retrieval_query("còn ô tô thì sao?", LICH_SU,
                           condense=lambda q, h: "x" * 500) == ghep

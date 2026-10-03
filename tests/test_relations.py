"""Quan hệ sửa đổi/thay thế đã xác minh cho các văn bản dùng trong demo."""
from server import number_chunks
from src.pipeline.relations import RELATIONS, relations_for


def test_moi_ban_sao_cua_cung_bo_luat_deu_tra_ra_quan_he():
    """BLDS 2015 nằm trong kho dưới 3 doc_id; cả 3 phải ra cùng một kết quả."""
    ids = ("91/2015/QH13", "Bo-luat-dan-su-2015-296215", "bo-luat-dan-su")
    results = [relations_for(i) for i in ids]
    assert results[0] and all(r == results[0] for r in results)
    assert "33/2005/QH11" in results[0][0]["text"]


def test_nd168_chi_sua_doi_mot_phan_nd100_khong_phai_thay_the():
    texts = " ".join(r["text"] for r in relations_for("congbao-43733"))
    assert "100/2019/NĐ-CP" in texts
    assert "thay thế" not in texts


def test_blhs_2015_biet_da_bi_luat_2017_sua_doi():
    texts = " ".join(r["text"] for r in relations_for("100/2015/QH13"))
    assert "12/2017/QH14" in texts


def test_moi_quan_he_deu_neu_can_cu_la_dieu_nao():
    for entry in RELATIONS:
        for r in entry["relations"]:
            assert r["basis"].startswith("Điều "), r


def test_van_ban_chua_xac_minh_tra_rong():
    assert relations_for("congbao-999999") == []
    assert relations_for("") == []


def test_number_chunks_gui_kem_quan_he_van_ban():
    chunk = {"chunk_id": "x", "doc_id": "52/2014/QH13", "title": "Luật HNGĐ",
             "law_type": "law", "score": 0.9, "text": "Điều 8."}
    out = number_chunks([chunk])[0]
    assert "22/2000/QH10" in out["relations"][0]["text"]
    assert number_chunks([{**chunk, "doc_id": "khac"}])[0]["relations"] == []


def test_luat_bhxh_cu_bi_thay_the_boi_ban_hop_nhat_2026():
    from src.pipeline.relations import SUPERSEDED
    for cu in ("Luat-Bao-hiem-xa-hoi-2014-259700", "luat-bao-hiem-xa-hoi"):
        assert SUPERSEDED[cu] == "congbao-468972"
        assert "Hết hiệu lực" in relations_for(cu)[0]["text"]
    assert "thay thế" in relations_for("congbao-468972")[0]["text"]


def test_van_ban_chi_sua_doi_mot_phan_khong_bi_loai_khoi_truy_xuat():
    from src.pipeline.relations import SUPERSEDED
    # NĐ 100/2019 chỉ bị NĐ 168 sửa một phần; BLHS 2015 bị Luật 2017 sửa vài điều.
    assert not set(SUPERSEDED) & {"congbao-43733", "100/2015/QH13", "bo-luat-hinh-su"}

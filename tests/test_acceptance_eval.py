"""Chấm một câu nghiệm thu: lấy đúng bằng chứng, trả lời đúng bằng chứng, từ chối/hỏi lại đúng lúc.

Không gọi model: kết quả sinh và chunk đều giả, chỉ kiểm logic chấm.
"""
from evaluation.acceptance_dataset import ACCEPTANCE
from evaluation.acceptance_eval import score_item, summarize
from src.generation.generator import CLARIFY_PREFIX, GAP_PREFIX

LAW = frozenset({"luat-x"})
RIGHT = {"doc_id": "luat-x", "article": 8, "text": "Điều 8. Nam từ đủ 20 tuổi, nữ từ đủ 18 tuổi"}
WRONG = {"doc_id": "luat-y", "article": 3, "text": "Điều 3. Chuyện khác"}


def item(kind="answer", **kw):
    base = {"id": "t", "split": "dev", "kind": kind, "question": "q",
            "expected": [(LAW, 8)], "must_contain": [["18 tuổi", "mười tám tuổi"]]}
    return {**base, **kw}


def result(answer, answered=True):
    return {"answer": answer, "answered": answered}


def test_tra_loi_dung_can_bang_chung_trich_dan_va_chi_tiet_mau_chot():
    s = score_item(item(), [WRONG, RIGHT], result("Nữ từ đủ 18 tuổi [2]."))
    assert s == {"evidence": True, "behavior": True, "grounded": True}


def test_trich_nham_nguon_thi_khong_tinh_la_dung_bang_chung():
    s = score_item(item(), [WRONG, RIGHT], result("Nữ từ đủ 18 tuổi [1]."))
    assert s["evidence"] is True and s["grounded"] is False


def test_thieu_chi_tiet_mau_chot_thi_khong_tinh():
    s = score_item(item(), [RIGHT], result("Nữ đủ tuổi thì được kết hôn [1]."))
    assert s["grounded"] is False


def test_chi_tiet_mau_chot_chap_nhan_cach_viet_khac():
    s = score_item(item(), [RIGHT], result("Nữ phải đủ mười tám tuổi [1]."))
    assert s["grounded"] is True


def test_khong_lay_duoc_bang_chung():
    s = score_item(item(), [WRONG], result("Nữ 18 tuổi [1]."))
    assert s["evidence"] is False and s["grounded"] is False


def test_cau_can_tra_loi_ma_model_tu_choi_la_sai_hanh_vi():
    s = score_item(item(), [RIGHT], result("Không có thông tin.", answered=False))
    assert s["behavior"] is False and s["grounded"] is False


def test_cau_thieu_du_kien_phai_hoi_lai():
    it = item("clarify", must_contain=[])
    hoi = result(f"Xe máy phạt X [1], ô tô phạt Y [1].\n{CLARIFY_PREFIX} bạn đi xe gì?")
    assert score_item(it, [RIGHT], hoi) == {"evidence": True, "behavior": True, "grounded": True}
    doan = result("Phạt X [1].")
    assert score_item(it, [RIGHT], doan)["behavior"] is False


def test_cau_tra_loi_thuong_tra_loi_xong_hoi_them_van_dung():
    s = score_item(item(), [RIGHT], result(f"Nữ 18 tuổi [1].\n{CLARIFY_PREFIX} gì?"))
    assert s == {"evidence": True, "behavior": True, "grounded": True}


def test_cau_khong_tra_loi_duoc_tu_choi_hoac_ghi_ro_phan_thieu_deu_dung():
    it = item("abstain", expected=[], must_contain=[])
    assert score_item(it, [WRONG], result("Không có.", answered=False)) == {
        "evidence": None, "behavior": True, "grounded": None}
    assert score_item(it, [WRONG], result(f"Luật nói chung [1].\n{GAP_PREFIX} số năm."))["behavior"]
    assert score_item(it, [WRONG], result("Cần 20 năm [1]."))["behavior"] is False


def test_tong_hop_theo_tap_va_bo_qua_chi_so_khong_ap_dung():
    rows = [
        {"split": "dev", "kind": "answer", "evidence": True, "behavior": True, "grounded": False},
        {"split": "dev", "kind": "abstain", "evidence": None, "behavior": False, "grounded": None},
        {"split": "holdout", "kind": "answer", "evidence": False, "behavior": True, "grounded": False},
    ]
    out = summarize(rows)
    assert out["dev"] == {"n": 2, "evidence": 1.0, "behavior": 0.5, "grounded": 0.0}
    assert out["holdout"]["evidence"] == 0.0
    assert out["all"]["n"] == 3


def test_bo_de_hop_le_va_co_tap_giu_rieng():
    ids = [q["id"] for q in ACCEPTANCE]
    assert len(ids) == len(set(ids))
    assert {q["split"] for q in ACCEPTANCE} == {"dev", "holdout"}
    for q in ACCEPTANCE:
        assert q["kind"] in {"answer", "clarify", "abstain"}
        assert bool(q["expected"]) == (q["kind"] != "abstain"), q["id"]
        for turn in q.get("history", []):
            assert turn["role"] in {"user", "assistant"}
    for split in ("dev", "holdout"):
        kinds = {q["kind"] for q in ACCEPTANCE if q["split"] == split}
        assert kinds == {"answer", "clarify", "abstain"}, split
        assert any(q.get("history") for q in ACCEPTANCE if q["split"] == split), split


def test_run_cho_roi_thu_lai_khi_truy_xuat_gap_429(monkeypatch):
    """Bước viết lại câu nối tiếp nằm trong retrieve, cũng có thể gặp 429."""
    from evaluation import acceptance_eval
    monkeypatch.setattr(acceptance_eval.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Pipe:
        class generator:
            @staticmethod
            def generate(q, chunks, history=None):
                return {"answer": "KHÔNG_TÌM_THẤY", "citations": [], "answered": False}

        def retrieve(self, q, history=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Error code: 429 - rate limit")
            return []

    item = {"id": "x", "split": "dev", "kind": "abstain", "question": "q",
            "expected": [], "must_contain": []}
    rows = acceptance_eval.run(Pipe(), [item], pause_s=0, wait_s=0)
    assert calls["n"] == 2 and rows[0]["id"] == "x"

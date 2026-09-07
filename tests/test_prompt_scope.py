"""Đoạn mô tả phạm vi kho phải sinh từ dữ liệu THẬT, không viết cứng.

Câu "Kho KHÔNG có nghị định" đúng khi kho chỉ có dữ liệu HuggingFace, nhưng
thành lời nói dối ngay khi crawl được nghị định đầu tiên - và hậu quả là model
trả KHÔNG_TÌM_THẤY cho đúng câu nó vừa trả lời được.
"""
from src.generation.generator import PROMPT_TEMPLATE, build_prompt, scope_paragraph


def test_says_missing_when_corpus_really_lacks_decrees():
    text = scope_paragraph({"law", "code", "constitution"})
    assert "nghị định" in text.lower()
    assert "KHÔNG có" in text


def test_stops_claiming_missing_once_decrees_are_indexed():
    text = scope_paragraph({"law", "code", "constitution", "decree"})
    assert "KHÔNG có nghị định" not in text
    assert "nghị định" in text.lower()  # vẫn phải kể ra là kho CÓ nghị định


def test_unknown_corpus_makes_no_claim_at_all():
    """Chưa biết kho có gì thì im lặng, thà thiếu thông tin còn hơn nói sai."""
    assert scope_paragraph(None) == ""
    assert scope_paragraph(set()) == ""


def test_prompt_embeds_the_scope_paragraph():
    prompt = build_prompt("Vượt đèn đỏ phạt bao nhiêu?", [
        {"title": "Nghị định 168/2024/NĐ-CP", "text": "Điều 6. Phạt tiền."}],
        law_types={"law", "decree"})
    assert "NGHỊ ĐỊNH" in prompt
    assert "KHÔNG có nghị định" not in prompt
    assert "Điều 6. Phạt tiền." in prompt


def test_doc_number_rule_allows_numbers_present_in_sources():
    """Cấm tuyệt đối số hiệu là sai khi kho đã có nghị định thật để trích."""
    assert "NGUYÊN VĂN trong các nguồn" in PROMPT_TEMPLATE

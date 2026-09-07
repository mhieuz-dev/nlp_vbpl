"""Parser cho congbao.chinhphu.vn - toàn hàm thuần, KHÔNG chạm mạng.

Fixture dựng theo đúng markup và đúng loại rác đã quan sát trên trang thật
(NĐ 168/2024/NĐ-CP, id 43733), không nhúng PDF thật để test chạy nhanh.
"""
from src.ingestion.chunker import chunk_documents
from src.ingestion.congbao import (
    clean_pdf_text,
    parse_detail,
    parse_rss,
    parse_slug,
    to_document,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
  <item>
    <link>https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-336-2026-nd-cp-470341.htm</link>
    <pubDate>Thu, 27 Aug 2026 00:00:00 GMT</pubDate>
  </item>
  <item>
    <link>https://congbao.chinhphu.vn/van-ban/thong-tu-so-119-2026-tt-bqp-470345.htm</link>
    <pubDate>Wed, 26 Aug 2026 00:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

# Trang văn bản thật: ngày neo vào nhãn "Ban hành:", và trang CÓ những ngày
# khác không được lấy nhầm (hiệu lực, ngày hôm nay, cả rác "24/12/4373").
SAMPLE_DETAIL_HTML = """<html><head>
<meta property="og:title" content="Ngh&#x1ECB; &#x111;&#x1ECB;nh s&#x1ED1; 168/2024/N&#x110;-CP quy &#x111;&#x1ECB;nh x&#x1EED; ph&#x1EA1;t vi ph&#x1EA1;m h&#xE0;nh ch&#xED;nh"/>
</head><body>
<span class="text"> Ban hành: 26/12/2024 <span> - Hiệu lực: 01/01/2025</span></span>
<div>Cập nhật 07/09/2026 - mã 24/12/4373</div>
<a href="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/12/43733/54010-1-a.pdf">Phần 1</a>
<a href="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/12/43733/54013-1-b.pdf">Phần 2</a>
<a href="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/12/43733/54010-1-a.pdf">trùng</a>
</body></html>"""

# Rác thật: header chạy có số trang hai bên, khối chữ ký số ở đầu file, và
# câu bị PDF ngắt dòng cứng giữa chừng.
SAMPLE_PDF_TEXT = """                    Người ký: CỔNG THÔNG TIN ĐIỆN TỬ CHÍNH PHỦ
                         Email: thongtinchinhphu@chinhphu.vn
                    Cơ quan: VĂN PHÒNG CHÍNH PHỦ
                    Thời gian ký: 12.02.2025 10:33:35 +07:00

2           CÔNG BÁO/Số 75 + 76/Ngày 16-01-2025

   Điều 6. Xử phạt người điều khiển xe ô tô, xe
chở người bốn bánh vi phạm quy tắc giao thông.
   9. Phạt tiền từ 18.000.000 đồng đến 20.000.000 đồng đối với người điều
khiển xe thực hiện hành vi vi phạm sau đây:
   b) Không chấp hành hiệu lệnh của đèn tín hiệu giao thông;

           CÔNG BÁO/Số 75 + 76/Ngày 16-01-2025               3

   Điều 7. Xử phạt người điều khiển xe mô tô.
   7. Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng.
"""


def test_parse_rss_gives_url_id_and_iso_date():
    items = parse_rss(SAMPLE_RSS)
    assert len(items) == 2
    assert items[0]["doc_id"] == "470341"
    assert items[0]["published"] == "2026-08-27"
    assert items[0]["url"].endswith("nghi-dinh-so-336-2026-nd-cp-470341.htm")


def test_parse_slug_reads_type_and_id():
    got = parse_slug("/van-ban/nghi-dinh-so-168-2024-nd-cp-43733.htm")
    assert got == {"doc_id": "43733", "law_type": "decree"}


def test_parse_slug_handles_extra_path_segment():
    """Link trong trang số Công báo có thêm một đoạn id nữa ở cuối."""
    got = parse_slug("/van-ban/nghi-dinh-so-336-2026-nd-cp-470341/67985.htm")
    assert got["doc_id"] == "470341"


def test_parse_slug_maps_other_types():
    assert parse_slug("/van-ban/thong-tu-so-119-2026-tt-bqp-470345.htm")["law_type"] == "circular"
    assert parse_slug("/van-ban/quyet-dinh-so-1624-qd-ttg-470337.htm")["law_type"] == "decision"
    assert parse_slug("/van-ban/van-ban-hop-nhat-so-16-2026-vbhn-tt-bkhcn-470370.htm")["doc_id"] == "470370"


def test_parse_slug_returns_none_on_junk():
    assert parse_slug("/cong-bao/cong-bao-so-498-ngay-04-09-2026-47437.htm") is None


def test_parse_detail_extracts_title_date_and_pdfs():
    d = parse_detail(SAMPLE_DETAIL_HTML)
    assert d["title"].startswith("Nghị định số 168/2024/NĐ-CP")
    assert d["doc_number"] == "168/2024/NĐ-CP"
    # phải neo vào nhãn "Ban hành", không lấy ngày hiệu lực hay ngày rác
    assert d["issue_date"] == "2024-12-26"
    assert len(d["pdf_urls"]) == 2  # bỏ link trùng, giữ thứ tự


def test_clean_pdf_text_drops_running_headers_and_signature():
    out = clean_pdf_text(SAMPLE_PDF_TEXT)
    assert "CÔNG BÁO/Số" not in out
    assert "Thời gian ký" not in out
    assert "thongtinchinhphu@chinhphu.vn" not in out
    assert "18.000.000" in out  # nội dung thật phải còn nguyên


def test_clean_pdf_text_rejoins_hard_wrapped_lines():
    """PDF ngắt dòng cứng giữa câu; không nối lại thì tên điều bị cụt."""
    out = clean_pdf_text(SAMPLE_PDF_TEXT)
    assert "xe ô tô, xe chở người bốn bánh" in out


def test_clean_pdf_text_keeps_dieu_at_line_start():
    """DIEU_PATTERN và ArticleIndex đều bám vào 'Điều N.' ở đầu dòng."""
    out = clean_pdf_text(SAMPLE_PDF_TEXT)
    for n in (6, 7):
        assert f"\nĐiều {n}." in "\n" + out


def test_to_document_matches_loader_contract():
    """chunk_documents đọc id/title/content/law_type bằng [], thiếu là KeyError."""
    doc = to_document(
        "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-168-2024-nd-cp-43733.htm",
        parse_detail(SAMPLE_DETAIL_HTML),
        clean_pdf_text(SAMPLE_PDF_TEXT),
    )
    assert doc["id"] == "congbao-43733"
    assert doc["law_type"] == "decree"
    assert doc["issue_date"] == "2024-12-26"
    assert doc["source_url"].endswith("-43733.htm")
    chunks = chunk_documents([doc])
    assert len(chunks) == 2  # cắt đúng theo Điều 6 / Điều 7
    assert chunks[0]["text"].startswith("Điều 6.")

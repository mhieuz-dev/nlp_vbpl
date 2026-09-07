"""Crawler Công báo - fetcher/sleeper/pdf đều tiêm vào nên KHÔNG chạm mạng."""
import json

import pytest

from src.ingestion.congbao import (
    BASE_URL, CrawlBlocked, Crawler, FeedEmpty, Response,
)

RSS_URL = f"{BASE_URL}/cac-van-ban-moi-ban-hanh.rss"
ND_URL = f"{BASE_URL}/van-ban/nghi-dinh-so-168-2024-nd-cp-43733.htm"
TT_URL = f"{BASE_URL}/van-ban/thong-tu-so-119-2026-tt-bqp-470345.htm"
PDF_A = "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/12/43733/a.pdf"
PDF_B = "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2026/08/470345/b.pdf"

RSS = f"""<rss><channel>
<item><link>{ND_URL}</link><pubDate>Thu, 26 Dec 2024 00:00:00 GMT</pubDate></item>
<item><link>{TT_URL}</link><pubDate>Wed, 27 Aug 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""


def detail(title, pdf):
    return f"""<html><head><meta property="og:title" content="{title}"/></head>
<body><span> Ban hành: 26/12/2024 </span><a href="{pdf}">tải</a></body></html>"""


PAGES = {
    RSS_URL: Response(200, {}, RSS.encode()),
    ND_URL: Response(200, {}, detail("Nghị định số 168/2024/NĐ-CP về giao thông", PDF_A).encode()),
    TT_URL: Response(200, {}, detail("Thông tư số 119/2026/TT-BQP về giảng dạy", PDF_B).encode()),
    PDF_A: Response(200, {}, b"%PDF-A"),
    PDF_B: Response(200, {}, b"%PDF-B"),
    f"{BASE_URL}/van-ban/x-43733.htm": Response(
        302, {"location": "/van-ban/nghi-dinh-so-168-2024-nd-cp-43733.htm"}, b""),
    f"{BASE_URL}/van-ban/x-99999.htm": Response(404, {}, b""),
}

PDF_TEXT = {
    b"%PDF-A": "Điều 6. Xử phạt ô tô.\n9. Phạt tiền từ 18.000.000 đồng.",
    b"%PDF-B": "Điều 1. Phạm vi điều chỉnh.\nThông tư này quy định về giảng dạy.",
}


class FakeFetcher:
    """Trả trang dựng sẵn, ghi lại thứ tự gọi để test kiểm tra."""

    def __init__(self, pages=None, fail=None):
        self.pages = dict(pages or PAGES)
        self.fail = fail or {}
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if url in self.fail:
            return self.fail[url]
        return self.pages.get(url, Response(404, {}, b""))


class FakeSleeper:
    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


def build(tmp_path, fetcher=None, **kw):
    return Crawler(
        fetch=fetcher or FakeFetcher(),
        sleep=FakeSleeper(),
        pdf_to_text=lambda b: PDF_TEXT.get(b, ""),
        state_path=tmp_path / "state.json",
        cache_dir=tmp_path / "cache",
        **kw,
    )


def test_crawl_recent_returns_documents(tmp_path):
    docs = build(tmp_path).crawl_recent()
    assert [d["id"] for d in docs] == ["congbao-43733", "congbao-470345"]
    assert docs[0]["law_type"] == "decree"
    assert "18.000.000" in docs[0]["content"]


def test_skips_documents_already_in_state(tmp_path):
    c = build(tmp_path)
    c.crawl_recent()
    again = build(tmp_path)
    assert again.crawl_recent() == []
    # lượt hai chỉ tốn đúng một request RSS
    assert again.fetch.calls == [RSS_URL]


def test_respects_max_docs(tmp_path):
    docs = build(tmp_path).crawl_recent(max_docs=1)
    assert len(docs) == 1


def test_filters_by_law_type(tmp_path):
    docs = build(tmp_path).crawl_recent(law_types={"decree"})
    assert [d["id"] for d in docs] == ["congbao-43733"]


def test_403_aborts_whole_crawl(tmp_path):
    """403 nghĩa là họ bắt đầu chặn; thử lại là phản ứng sai."""
    f = FakeFetcher(fail={ND_URL: Response(403, {}, b"")})
    c = build(tmp_path, fetcher=f)
    with pytest.raises(CrawlBlocked):
        c.crawl_recent()
    assert TT_URL not in f.calls  # dừng hẳn, không chạy tiếp văn bản sau


def test_state_saved_after_each_document(tmp_path):
    """Bị kill giữa chừng thì phần đã xong phải còn nguyên để chạy tiếp."""
    f = FakeFetcher(fail={PDF_B: Response(500, {}, b"")})
    c = build(tmp_path, fetcher=f)
    c.crawl_recent()
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["43733"]["status"] == "ok"
    assert state["470345"]["status"] == "error"


def test_waits_between_requests(tmp_path):
    c = build(tmp_path)
    c.crawl_recent()
    assert c.sleep.waits, "phải có nghỉ giữa các request"
    assert min(c.sleep.waits) >= 2.0


def test_unchanged_pdf_is_skipped(tmp_path):
    c = build(tmp_path)
    c.crawl_recent()
    again = build(tmp_path)
    assert again.fetch_document(ND_URL) is None  # sha256 không đổi


def test_resolve_id_reads_canonical_slug_from_redirect(tmp_path):
    c = build(tmp_path)
    assert c.resolve_id("43733") == ND_URL
    assert c.resolve_id("99999") is None


def test_cache_avoids_refetching_bytes(tmp_path):
    build(tmp_path).crawl_recent()
    c2 = build(tmp_path)
    c2.state = {}  # quên state, nhưng cache bytes vẫn còn
    c2.crawl_recent()
    assert ND_URL not in c2.fetch.calls


def test_empty_rss_is_treated_as_broken_not_as_no_news(tmp_path):
    """RSS luôn có 50 item. Trả 0 nghĩa là họ đổi format, không phải hết tin.

    Không phân biệt hai ca này thì lượt chạy tự động sẽ báo "không có gì mới"
    êm ru trong nhiều tháng trong khi thật ra đã hỏng từ lâu.
    """
    f = FakeFetcher(pages={RSS_URL: Response(200, {}, b"<rss><channel></channel></rss>")})
    with pytest.raises(FeedEmpty):
        build(tmp_path, fetcher=f).crawl_recent()


def test_rss_with_items_is_fine(tmp_path):
    """Có item nhưng đều đã nạp rồi thì đó THẬT SỰ là không có gì mới."""
    c = build(tmp_path)
    c.crawl_recent()
    assert build(tmp_path).crawl_recent() == []


def test_user_agent_contact_comes_from_env(monkeypatch):
    """Email liên hệ phải đổi được mà không sửa mã nguồn.

    Repo private thì để email cá nhân không sao, nhưng HF Space là công khai.
    Đồng thời User-Agent vẫn phải LUÔN có một địa chỉ liên hệ - đó là phép lịch
    sự tối thiểu khi crawl, và robots.txt của họ cho phép chính vì vậy.
    """
    from src.ingestion import congbao

    monkeypatch.setenv("CRAWLER_CONTACT", "lienhe@vidu.vn")
    ua = congbao.user_agent()
    assert "lienhe@vidu.vn" in ua
    assert "LuatAI" in ua

    monkeypatch.delenv("CRAWLER_CONTACT", raising=False)
    assert "contact" in congbao.user_agent().lower()

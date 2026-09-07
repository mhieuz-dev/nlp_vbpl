"""Đọc văn bản từ Công báo điện tử (congbao.chinhphu.vn).

Vì sao nguồn này: `vbpl.vn` chặn crawl bằng WAF, còn đây trả HTTP 200 với
`robots.txt: User-agent: * / Allow: /`, có nghị định, và cập nhật tới hôm nay.

Toàn văn KHÔNG nằm trong HTML mà trong PDF đính kèm, nên đường đi là
trang văn bản -> URL PDF -> bóc text -> `clean_pdf_text` -> `to_document`.

Ô tra cứu của site đã hỏng (`/tim-kiem?keyword=...` trả 302 về `/` với mọi từ
khoá), nên định vị văn bản cũ bằng cách dò id: `/van-ban/x-{id}.htm` chấp nhận
slug sai, chỉ cần id đúng, rồi trả 302 với slug canonical trong header
`Location`. Slug đó đã có sẵn loại văn bản và số hiệu nên lọc được TRƯỚC khi
tải trang, mà mỗi lần tra tốn 0 byte.

Mọi hàm ở đây đều thuần: nhận chuỗi, trả dữ liệu. Phần đi mạng nằm riêng.
"""
import hashlib
import html as html_mod
import json
import re
import time
from collections import namedtuple
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE_URL = "https://congbao.chinhphu.vn"

# Tiếng Anh cho khớp với `law`/`code`/`constitution` đã có sẵn trong kho.
LAW_TYPES = {
    "luat": "law",
    "bo-luat": "code",
    "hien-phap": "constitution",
    "nghi-dinh": "decree",
    "nghi-quyet": "resolution",
    "thong-tu": "circular",
    "thong-tu-lien-tich": "circular",
    "quyet-dinh": "decision",
    "chi-thi": "directive",
    "phap-lenh": "ordinance",
    "van-ban-hop-nhat": "consolidated",
}

# "/van-ban/nghi-dinh-so-168-2024-nd-cp-43733.htm" -> ("nghi-dinh", "43733").
# Đoạn "/67985" ở cuối là id của văn bản trong một số Công báo cụ thể, có ở
# link đi từ trang số Công báo nhưng không có ở link đi từ trang liệt kê.
_SLUG_RE = re.compile(r"/van-ban/([a-z\-]+?)-so-[^/]*?-(\d+)(?:/\d+)?\.htm")

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
_LINK_RE = re.compile(r"<link>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</link>", re.S)
_PUBDATE_RE = re.compile(r"<pubDate>\s*(.*?)\s*</pubDate>", re.S)

_OG_TITLE_RE = re.compile(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"')
# Phải neo vào nhãn "Ban hành": trang còn có ngày hiệu lực, ngày hôm nay, và
# cả ngày rác kiểu "24/12/4373". Lấy "ngày đầu tiên gặp" là sai.
_ISSUE_DATE_RE = re.compile(r"Ban\s+h[àa]nh:?\s*(\d{2})/(\d{2})/(\d{4})")
_PDF_RE = re.compile(r"https://congbaocdn[^\"'\s\\<>]+\.pdf")
_DOC_NUMBER_RE = re.compile(r"\bsố\s+(\S+/\S+)", re.IGNORECASE)

# Rác lặp trong PDF Công báo: header chạy (128 lần trong NĐ 168/2024) và khối
# chữ ký số ở đầu file.
_JUNK_LINE_RE = re.compile(
    r"CÔNG BÁO\s*/\s*Số|Người ký:|Thời gian ký:|Cơ quan:\s*VĂN PHÒNG|Email:\s*\S+@"
)
_PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")


def parse_slug(url: str) -> dict | None:
    """URL trang văn bản -> {doc_id, law_type}. Trả None nếu không phải."""
    m = _SLUG_RE.search(url)
    if not m:
        return None
    return {"doc_id": m.group(2), "law_type": LAW_TYPES.get(m.group(1), "other")}


def parse_rss(xml: str) -> list[dict]:
    """RSS văn bản mới -> [{url, doc_id, published}], bỏ item không phải văn bản."""
    items = []
    for block in _ITEM_RE.findall(xml):
        link = _LINK_RE.search(block)
        if not link:
            continue
        url = link.group(1).strip()
        slug = parse_slug(url)
        if not slug:
            continue
        pub = _PUBDATE_RE.search(block)
        items.append({
            "url": url,
            "doc_id": slug["doc_id"],
            "published": _rfc822_to_iso(pub.group(1)) if pub else "",
        })
    return items


def parse_detail(html: str) -> dict:
    """Trang văn bản -> {title, doc_number, issue_date, pdf_urls}.

    Không bao giờ ném lỗi: thiếu trường nào thì trường đó là chuỗi rỗng. Một
    văn bản thiếu ngày vẫn nạp được, còn hơn làm hỏng cả lượt crawl.
    """
    og = _OG_TITLE_RE.search(html)
    title = html_mod.unescape(og.group(1)).strip() if og else ""

    num = _DOC_NUMBER_RE.search(title)
    date = _ISSUE_DATE_RE.search(html)

    # Văn bản dài bị chia thành nhiều PDF (NĐ 168/2024 có 2 phần), phải giữ
    # đủ và đúng thứ tự; dict.fromkeys để bỏ trùng mà không đảo thứ tự.
    pdfs = list(dict.fromkeys(_PDF_RE.findall(html)))

    return {
        "title": title,
        "doc_number": num.group(1) if num else "",
        "issue_date": f"{date.group(3)}-{date.group(2)}-{date.group(1)}" if date else "",
        "pdf_urls": pdfs,
    }


def clean_pdf_text(text: str) -> str:
    """Bỏ rác của bản PDF và nối lại những câu bị ngắt dòng cứng.

    Nối dòng là cần thiết chứ không phải làm đẹp: PDF ngắt dòng ở ~75 ký tự
    nên tên điều bị cắt làm đôi, mà `_split_oversize` lấy header chỉ trong
    phạm vi một dòng.
    """
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or _PAGE_NUMBER_RE.match(line) or _JUNK_LINE_RE.search(line):
            lines.append("")
            continue
        lines.append(line)

    out: list[str] = []
    for line in lines:
        # Nối khi dòng trước chưa kết thúc ý và dòng này bắt đầu bằng chữ
        # thường - dấu hiệu chắc chắn nhất của một câu bị ngắt giữa chừng.
        if out and out[-1] and line and out[-1][-1] not in ".;:!?" and line[:1].islower():
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def to_document(url: str, detail: dict, content: str) -> dict:
    """Ghép thành dict đúng giao kèo của `chunk_documents`.

    `loader.py` đọc id/title/content/law_type bằng [] nên thiếu key là
    KeyError. Ba key còn lại là metadata cho vectorstore.
    """
    slug = parse_slug(url)
    if slug is None:
        raise ValueError(f"Không phải URL trang văn bản: {url}")
    return {
        "id": f"congbao-{slug['doc_id']}",
        "title": detail["title"],
        "content": content,
        "law_type": slug["law_type"],
        "issue_date": detail["issue_date"],
        "doc_number": detail["doc_number"],
        "source_url": url,
    }


def _rfc822_to_iso(value: str) -> str:
    """'Thu, 27 Aug 2026 00:00:00 GMT' -> '2026-08-27'. Hỏng thì trả rỗng."""
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


# ---------------------------------------------------------------------------
# Phần đi mạng. Fetcher / sleeper / bộ bóc PDF đều tiêm vào để test không cần
# mạng, không cần pymupdf, và chạy trong mili giây.
# ---------------------------------------------------------------------------

RSS_PATH = "/cac-van-ban-moi-ban-hanh.rss"

# Tự xưng thật, có địa chỉ liên hệ. robots.txt của họ cho phép (`Allow: /`)
# nên không có lý do gì phải giả trình duyệt.
USER_AGENT = (
    "LuatAI-student-research/0.1 "
    "(NLP coursework; contact huggingface.co/spaces/mhieuzzz/nlp-vbpl)"
)

HTML_DELAY = 2.0
PDF_DELAY = 4.0
# Dò id chỉ đọc header 302, tải 0 byte, nên nhẹ hơn hẳn một lượt tải trang.
PROBE_DELAY = 1.5

Response = namedtuple("Response", "status headers body")


class CrawlBlocked(RuntimeError):
    """Máy chủ trả 403 - họ bắt đầu chặn. Dừng cả lượt, không thử lại."""


class FetchError(RuntimeError):
    """Một văn bản hỏng. Ghi nhận rồi đi tiếp, không làm chết cả lượt."""


class FeedEmpty(RuntimeError):
    """RSS không ra item nào - họ đổi format, chứ không phải hết tin."""


class Crawler:
    def __init__(self, fetch, *, sleep=time.sleep, pdf_to_text=None,
                 state_path=None, cache_dir=None):
        self.fetch = fetch
        self.sleep = sleep
        self.pdf_to_text = pdf_to_text or pdf_bytes_to_text
        self.state_path = Path(state_path) if state_path else None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.state = self._load_state()

    # -- công khai ---------------------------------------------------------

    def crawl_recent(self, max_docs: int | None = 50,
                     law_types: set[str] | None = None) -> list[dict]:
        """Văn bản mới trong RSS. Đây là đường cho lượt chạy hàng ngày."""
        body = self._get(f"{BASE_URL}{RSS_PATH}", HTML_DELAY)
        items = parse_rss(body.decode("utf-8", "replace"))
        # Feed luôn có 50 item. Rỗng nghĩa là họ đổi format, và im lặng coi đó
        # là "hết tin" sẽ khiến lượt chạy tự động báo yên ổn suốt nhiều tháng
        # trong khi thật ra đã hỏng từ lâu.
        if not items:
            raise FeedEmpty(f"{BASE_URL}{RSS_PATH} không ra item nào")
        return self._crawl_urls([i["url"] for i in items], max_docs, law_types)

    def crawl_ids(self, doc_ids, max_docs: int | None = None,
                  law_types: set[str] | None = None) -> list[dict]:
        """Dò một dải id. Đây là đường backfill có chủ đích.

        Lọc theo `law_types` xảy ra ngay trên slug lấy được từ header 302,
        nên văn bản không quan tâm thì không tốn lượt tải trang nào.
        """
        urls = []
        for doc_id in doc_ids:
            if max_docs is not None and len(urls) >= max_docs:
                break
            url = self.resolve_id(str(doc_id))
            if url and (not law_types or parse_slug(url)["law_type"] in law_types):
                urls.append(url)
        return self._crawl_urls(urls, max_docs, law_types)

    def resolve_id(self, doc_id: str) -> str | None:
        """id -> URL canonical, đọc từ header `Location` của 302. Tải 0 byte."""
        self.sleep(PROBE_DELAY)
        res = self.fetch(f"{BASE_URL}/van-ban/x-{doc_id}.htm")
        if res.status == 403:
            raise CrawlBlocked(f"403 khi dò id {doc_id}")
        location = (res.headers or {}).get("location", "")
        if res.status in (301, 302) and parse_slug(location):
            return location if location.startswith("http") else BASE_URL + location
        return None

    def fetch_document(self, url: str) -> dict | None:
        """Tải + bóc một văn bản. Trả None nếu PDF không đổi so với lần trước."""
        slug = parse_slug(url)
        if slug is None:
            return None
        doc_id = slug["doc_id"]

        html = self._get(url, HTML_DELAY, f"{doc_id}.html")
        detail = parse_detail(html.decode("utf-8", "replace"))
        if not detail["pdf_urls"]:
            raise FetchError(f"{url}: trang không có PDF đính kèm")

        blobs = [self._get(p, PDF_DELAY, f"{doc_id}-{i}.pdf")
                 for i, p in enumerate(detail["pdf_urls"])]

        # PDF Công báo bất biến sau khi công bố, nên hash không đổi là bỏ qua
        # được cả bóc text lẫn embed - lượt chạy hàng ngày gần như miễn phí.
        digest = hashlib.sha256(b"".join(blobs)).hexdigest()
        seen = self.state.get(doc_id, {})
        if seen.get("status") == "ok" and seen.get("sha256") == digest:
            return None

        text = clean_pdf_text("\n".join(self.pdf_to_text(b) for b in blobs))
        doc = to_document(url, detail, text)
        doc["sha256"] = digest
        return doc

    # -- nội bộ ------------------------------------------------------------

    def _crawl_urls(self, urls, max_docs, law_types) -> list[dict]:
        docs = []
        for url in urls:
            if max_docs is not None and len(docs) >= max_docs:
                break
            slug = parse_slug(url)
            if slug is None:
                continue
            if law_types and slug["law_type"] not in law_types:
                continue
            doc_id = slug["doc_id"]
            if self.state.get(doc_id, {}).get("status") == "ok":
                continue
            try:
                doc = self.fetch_document(url)
            except FetchError as exc:
                self._record(doc_id, {"status": "error", "url": url, "error": str(exc)})
                continue
            if doc is None:
                continue
            docs.append(doc)
            self._record(doc_id, {
                "status": "ok",
                "url": url,
                "sha256": doc["sha256"],
                "issue_date": doc["issue_date"],
                "law_type": doc["law_type"],
                "chars": len(doc["content"]),
            })
        return docs

    def _get(self, url: str, delay: float, cache_name: str | None = None) -> bytes:
        """Tải một URL, ưu tiên cache bytes thô đã lưu.

        Cache là thứ đáng giá nhất ở đây: chỉnh lại bộ lọc rác rồi chạy lại
        hàng chục lần mà không tốn một request nào của họ.
        """
        cached = self.cache_dir / cache_name if (self.cache_dir and cache_name) else None
        if cached is not None and cached.exists():
            return cached.read_bytes()

        self.sleep(delay)
        res = self.fetch(url)
        if res.status == 403:
            raise CrawlBlocked(f"403 tại {url} - dừng cả lượt crawl")
        if res.status != 200:
            raise FetchError(f"{url}: HTTP {res.status}")

        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(res.body)
        return res.body

    def _record(self, doc_id: str, entry: dict) -> None:
        """Ghi state sau MỖI văn bản, để bị kill giữa chừng vẫn chạy tiếp được."""
        entry["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.state[doc_id] = entry
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    def _load_state(self) -> dict:
        if self.state_path and self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}


def pdf_bytes_to_text(data: bytes) -> str:
    """Bóc text PDF. `sort=True` để bảng mức phạt không bị xáo thứ tự đọc."""
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text("text", sort=True) for page in doc)


# Chỉ thử lại với lỗi tạm thời. 403 KHÔNG nằm ở đây: đó là họ chặn, thử lại
# là phản ứng sai và còn làm tình hình tệ hơn.
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRY_DELAYS = (2.0, 8.0, 30.0)


def http_fetcher(timeout: float = 30.0):
    """Fetcher thật cho `Crawler`. Không tự đi theo redirect vì `resolve_id`
    cần đọc chính header `Location` đó."""
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    def fetch(url: str) -> Response:
        last = None
        for attempt, wait in enumerate((0.0,) + RETRY_DELAYS):
            if wait:
                time.sleep(wait)
            try:
                res = session.get(url, timeout=timeout, allow_redirects=False)
            except requests.RequestException as exc:
                last = Response(0, {}, str(exc).encode())
                continue
            if res.status_code not in RETRY_STATUSES:
                headers = {k.lower(): v for k, v in res.headers.items()}
                return Response(res.status_code, headers, res.content)
            last = Response(res.status_code, {}, b"")
        return last

    return fetch

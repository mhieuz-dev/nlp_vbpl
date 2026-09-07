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
import html as html_mod
import re
from email.utils import parsedate_to_datetime

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

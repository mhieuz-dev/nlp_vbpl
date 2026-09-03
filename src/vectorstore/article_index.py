"""Tra cứu điều luật theo số, cho những câu hỏi nêu đích danh "Điều N".

Vì sao cần: embedding dense gần như vô dụng với loại câu hỏi này. Đo thật trên
kho 48.803 chunk, "Điều 630 Bộ luật Dân sự nói về vấn đề gì?" không đưa được
Điều 630 vào cả top-30.

Vì sao không dùng BM25: đã thử và đo. BM25 ngốn thêm 1,5 GB RAM, và vẫn sai
đúng loại câu này - hỏi "Điều 117" thì nó trả Điều 122, vì thân Điều 122 có
nhắc "quy định tại Điều 117". Nó không phân biệt "đây LÀ điều 117" với "xem
thêm điều 117". Chỉ mục dưới đây chỉ giữ phần đầu mỗi chunk nên tốn khoảng
15 MB, và phân biệt được đúng chỗ đó.
"""
import re
import unicodedata

# "Điều 117 Bộ luật Dân sự", "điều 9,", "Điều 630." - số phải đi liền sau chữ Điều
_REF_RE = re.compile(r"\bĐiều\s+(\d+)", re.IGNORECASE | re.UNICODE)
# Phần đầu chunk: "Điều 117. Điều kiện có hiệu lực..."
_HEADER_RE = re.compile(r"^\s*Điều\s+(\d+)\.")


def _norm(text: str) -> str:
    """Bỏ dấu tiếng Việt (kể cả đ) và chữ số, để so tên luật bất kể cách viết."""
    t = text.lower().replace("đ", "d")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"\d+", " ", t)).strip()


def parse_article_ref(question: str):
    """('Điều 117 Bộ luật Dân sự quy định gì?') -> (117, 'bo luat dan su').

    Trả None khi câu hỏi không nêu đích danh điều nào. Gợi ý tên luật là phần
    chữ ngay sau số điều, cắt tới dấu câu hoặc từ nghi vấn đầu tiên.
    """
    m = _REF_RE.search(question)
    if not m:
        return None
    tail = question[m.end():]
    tail = re.split(r"[,.?;:]| quy định| nói| là gì| có nội dung| gồm", tail)[0]
    law = _norm(tail)
    return int(m.group(1)), (law or None)


class ArticleIndex:
    """(tên luật đã chuẩn hoá, số điều) -> danh sách chunk_id."""

    PAGE = 5000

    def __init__(self, collection):
        self._by_article = {}
        self._build(collection)

    def _build(self, collection):
        total = collection.count()
        offset = 0
        while offset < total:
            page = collection.get(
                include=["documents", "metadatas"], limit=self.PAGE, offset=offset
            )
            for cid, doc, meta in zip(page["ids"], page["documents"], page["metadatas"]):
                m = _HEADER_RE.match(doc)
                if not m:
                    continue
                self._by_article.setdefault(int(m.group(1)), []).append(
                    (_norm(meta.get("title", "")), cid)
                )
            offset += self.PAGE

    def find(self, article: int, law_hint: str | None) -> list[str]:
        entries = self._by_article.get(article, [])
        if law_hint:
            hint = _norm(law_hint)
            entries = [e for e in entries if hint and hint in e[0]]
        return [cid for _, cid in entries]

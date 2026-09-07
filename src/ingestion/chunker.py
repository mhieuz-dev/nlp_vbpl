"""Cắt văn bản luật thành chunk để embed.

Đơn vị cắt là ĐIỀU LUẬT, không phải cửa sổ ký tự: một điều là một ý pháp lý
trọn vẹn, cắt giữa điều thì cả hai mảnh đều mất nghĩa.

Vì sao 1.500 ký tự: e5-base cắt cụt ở 512 TOKEN. Đo trên chính kho này, văn
bản luật tiếng Việt tốn ~3,48 ký tự/token, tức 512 token ~ 1.780 ký tự. Lấy
1.500 để chừa chỗ cho header ghép thêm ở _split_oversize mà vẫn dưới trần.
(Giá trị cũ là 512 - viết như thể là ký tự nhưng thật ra giới hạn tính bằng
token, nên cắt vụn gấp ~3,5 lần mức cần thiết.)
"""
import re

DIEU_PATTERN = re.compile(r"(?=Điều\s+\d+\.)", re.UNICODE)
MAX_CHUNK_SIZE = 1500
OVERLAP = 100

# Header của điều: "Điều 66." cộng tối đa 100 ký tự tên điều. Giới hạn 100 là
# cần thiết - text bóc từ PDF có thể cả trang không xuống dòng, nếu lấy [^\n]*
# thì "header" phình ra hàng nghìn ký tự và không còn chỗ cho nội dung.
_DIEU_HEADER_RE = re.compile(r"^\s*(Điều\s+\d+\.)([^\n]{0,100})")
# Đầu mỗi khoản: "1. ", "12. " ở đầu dòng.
_KHOAN_RE = re.compile(r"(?m)^(?=\s*\d+\.\s)")


def chunk_documents(docs: list[dict]) -> list[dict]:
    chunks = []
    for doc in docs:
        content = doc["content"]
        raw_chunks = _split_by_dieu(content) or _split_by_size(content)

        pieces = []
        for part in raw_chunks:
            if len(part) > MAX_CHUNK_SIZE:
                pieces.extend(_split_oversize(part))
            else:
                pieces.append(part)

        for i, text in enumerate(pieces):
            text = text.strip()
            if not text:
                continue
            chunks.append({
                "chunk_id": f"{doc['id']}_{i}",
                "doc_id": doc["id"],
                "title": doc["title"],
                "law_type": doc["law_type"],
                "text": text,
                "char_start": content.find(text),
                # Văn bản từ HuggingFace không có ba trường này; .get để chúng
                # đi được tới vectorstore mà không làm vỡ đường nạp cũ.
                "issue_date": doc.get("issue_date", ""),
                "source_url": doc.get("source_url", ""),
                "doc_number": doc.get("doc_number", ""),
            })
    return chunks


def _split_by_dieu(text: str) -> list[str]:
    parts = DIEU_PATTERN.split(text)
    return [p for p in parts if p.strip()]


def _split_oversize(text: str) -> list[str]:
    """Cắt một điều quá dài thành nhiều mảnh, theo ranh giới KHOẢN.

    Mọi mảnh đều được ghép lại header "Điều N." ở đầu. Bắt buộc: ArticleIndex
    nhận diện chunk bằng `^\\s*Điều\\s+(\\d+)\\.`, mảnh nào mất header thì vô
    hình với tra cứu theo số điều - tính năng đã nâng Recall@5 từ 0,773 lên
    0,864 nên không được làm hỏng.
    """
    m = _DIEU_HEADER_RE.match(text)
    header = (m.group(1) + m.group(2)).strip() if m else ""
    # Chừa sẵn chỗ cho header + "\n" để mảnh sau khi ghép vẫn <= MAX_CHUNK_SIZE.
    room = MAX_CHUNK_SIZE - (len(header) + 1 if header else 0)

    units = []
    for part in (p.strip() for p in _KHOAN_RE.split(text)):
        if not part:
            continue
        # Khoản nào tự nó đã quá dài (bảng mức phạt dài, điều không đánh khoản)
        # thì đành cắt cứng theo cửa sổ - hết cách bám vào cấu trúc.
        units.extend(_split_by_size(part, room) if len(part) > room else [part])

    groups, cur = [], ""
    for unit in units:
        if cur and len(cur) + 1 + len(unit) > room:
            groups.append(cur)
            cur = unit
        else:
            cur = f"{cur}\n{unit}" if cur else unit
    if cur:
        groups.append(cur)

    # groups[0] đã bắt đầu bằng header sẵn (nó chính là phần đầu của điều).
    return groups[:1] + [f"{header}\n{g}" if header else g for g in groups[1:]]


def _split_by_size(text: str, size: int = MAX_CHUNK_SIZE) -> list[str]:
    """Cắt theo cửa sổ trượt, có chồng lấn OVERLAP ký tự.

    Bug cũ: `start = end - OVERLAP` đứng yên khi end == len(text), vòng lặp
    chạy vô hạn và list phình tới khi hết RAM. Chỉ đúng một input duy nhất
    thoát được là chuỗi rỗng, nên test cũ không bao giờ chạm phải.
    """
    step = max(1, size - OVERLAP)
    out = []
    start = 0
    while start < len(text):
        out.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += step
    return out

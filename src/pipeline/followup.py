"""Xử lý câu hỏi nối tiếp trong một cuộc hội thoại.

Bài toán: "Vượt đèn đỏ phạt bao nhiêu?" rồi hỏi tiếp "còn ô tô thì sao?".
Câu thứ hai tự nó không mang đủ nghĩa - đem đi nhúng thì vector rơi vào vùng
chẳng liên quan gì tới giao thông, và kho trả về điều luật sai.

Cách giải KHÔNG dùng ở đây: nhờ LLM viết lại câu hỏi. Đã đo trên chính dự án
này, Recall@5 tụt từ 0,864 xuống 0,545 - model viết lại làm mất từ khoá pháp
lý và thêm chữ thừa, đẩy vector đi xa. Ngoài ra nó thêm một lượt gọi API vào
đường truy xuất, tức thêm độ trễ và thêm tiền.

Cách dùng ở đây: ghép câu hỏi trước vào câu hiện tại để nhúng, và CHỈ ghép khi
câu hiện tại trông như câu nối tiếp. Câu hỏi đứng một mình vẫn đi nguyên vẹn,
nên bộ đánh giá Recall cũ (22 câu, đều đứng một mình) không đổi một chữ.
"""
import re

# Dấu hiệu câu dựa vào ngữ cảnh trước đó: từ nối, đại từ thay thế, câu cụt.
_FOLLOWUP_MARKERS = (
    "còn", "vậy", "thế", "thì sao", "vậy còn", "nếu vậy", "ngược lại",
    "trường hợp này", "trường hợp đó", "cái đó", "cái này", "điều đó",
    "nó", "mức đó", "như vậy", "tương tự", "ngoài ra", "thêm nữa",
)

# Câu ngắn hơn ngưỡng này gần như chắc chắn không đứng một mình được.
_SHORT_WORDS = 6

_CITE_RE = re.compile(r"\[\d+\]")


def is_followup(question: str) -> bool:
    """Câu hỏi này có cần ngữ cảnh của lượt trước mới hiểu được không?

    Luật xác định, không gọi model. Sai về phía nào cũng chịu được: nhận nhầm
    câu độc lập thành nối tiếp thì chỉ thêm ít chữ vào truy vấn; bỏ sót câu
    nối tiếp thì tệ hơn, nên ngưỡng đặt rộng tay một chút.
    """
    q = question.strip().lower()
    if not q:
        return False
    if len(q.split()) <= _SHORT_WORDS:
        return True
    return any(
        re.search(r"(?:^|\s)" + re.escape(m) + r"(?:\s|$|\?|,)", q)
        for m in _FOLLOWUP_MARKERS
    )


def _ghep(question: str, history) -> str:
    """Cách dự phòng khi không viết lại được: ghép câu hỏi trước vào.

    Kém hơn hẳn viết lại, và đã đo được vì sao: với "Vượt đèn đỏ xe máy phạt
    bao nhiêu?" rồi "còn ô tô thì sao?", chuỗi ghép vẫn mang cụm "xe máy" nên
    kho trả về Điều 7 (xe máy) và KHÔNG có Điều 6 (ô tô) trong top 5. Vẫn giữ
    làm đường lui vì nó không cần mạng và không bao giờ hỏng.
    """
    for turn in reversed(history):
        if turn.get("role") == "user" and turn.get("content", "").strip():
            return turn["content"].strip() + " " + question
    return question


def retrieval_query(question: str, history, condense=None) -> str:
    """Câu dùng để NHÚNG và tìm trong kho (khác câu gửi cho model đọc).

    Lịch sử rỗng hoặc câu tự đứng được thì trả nguyên câu hỏi - đây là đường đi
    của mọi câu đầu tiên và của toàn bộ bộ đánh giá Recall, nên số 0,864 đo
    trước đây vẫn nói đúng về hệ thống này.

    `condense` tiêm vào để test khỏi chạm mạng; thiếu nó hoặc nó hỏng thì lui
    về cách ghép chuỗi.
    """
    question = question.strip()
    if not history or not is_followup(question):
        return question

    if condense is not None:
        try:
            viet_lai = (condense(question, history) or "").strip()
        except Exception:
            viet_lai = ""     # viết lại hỏng thì vẫn phải trả lời được câu hỏi
        # Chặn kết quả vô lý: rỗng, hoặc dài bất thường nghĩa là model đã kể lể
        # thay vì viết một câu hỏi.
        if viet_lai and len(viet_lai) <= 300:
            return viet_lai

    return _ghep(question, history)



def strip_citations(text: str) -> str:
    """Bóc số dẫn nguồn khỏi câu trả lời cũ trước khi đưa vào lịch sử.

    Bẫy thật: câu trả lời lượt trước chứa [3], [8] trỏ tới cách đánh số nguồn
    CỦA LƯỢT ĐÓ. Lượt mới truy xuất lại, [3] bây giờ là điều luật khác. Để
    nguyên thì model thấy mẫu "[3]" trong hội thoại và bê lại số cũ, tạo ra
    trích dẫn trỏ sai điều - kiểu sai tệ nhất với một hệ thống tra cứu luật,
    vì nó trông vẫn rất đáng tin.
    """
    return _CITE_RE.sub("", text)

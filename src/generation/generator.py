"""Sinh câu trả lời qua API tương thích OpenAI.

Dùng client OpenAI-compatible thay vì SDK riêng của từng hãng, nên đổi nhà
cung cấp chỉ bằng ba biến môi trường:

    LLM_BASE_URL   endpoint (mặc định: Gemini qua lớp tương thích OpenAI)
    LLM_MODEL      tên model
    LLM_API_KEY    khoá (thiếu thì lấy GEMINI_API_KEY cho tương thích ngược)

Ví dụ chuyển sang Groq (free, không cần thẻ):
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_MODEL=llama-3.3-70b-versatile
"""
import logging
import os

from src.pipeline.followup import strip_citations

logger = logging.getLogger(__name__)
import re
import time

from openai import OpenAI

_CITE_RE = re.compile(r"\[(\d+)\]")

# Model suy nghĩ (qwen3.6 trên Groq) rò khối lý luận tiếng Anh vào câu trả lời.
# Bỏ cả trường hợp thẻ mở không có thẻ đóng (phản hồi bị cắt giữa chừng).
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)

# Ngưỡng điểm KHÔNG chặn được câu không trả lời được: điểm của câu trả lời được
# (0,861-0,890) chồng lấn câu không trả lời được (0,843-0,864). Nên để chính
# model phán đoán, đánh dấu bằng một dòng máy đọc được.
NO_ANSWER_MARKER = "KHÔNG_TÌM_THẤY"

# Trần ngữ cảnh gửi cho model, tính bằng KÝ TỰ (không phải token) để không phải
# nạp tokenizer. Đo thật trên văn bản luật tiếng Việt: 3,48 ký tự/token.
#
# Groq free tier: 8.000 token/phút, tính CẢ input lẫn output. Trừ ~800 token cho
# câu trả lời và ~450 token cho phần hướng dẫn trong prompt, còn ~6.750 token cho
# ngữ cảnh. Lấy 16.000 ký tự (~4.600 token) để còn dư cho cửa sổ trượt khi người
# dùng hỏi liên tiếp.
#
# Vì sao cần: điều luật dài rất chênh nhau (118 - 3.163 ký tự). Câu "nồng độ cồn
# bao nhiêu thì bị phạt" truy xuất trúng 10 điều dài -> 26.887 ký tự -> lỗi 413.
MAX_CONTEXT_CHARS = 16000


def fit_to_context(chunks: list[dict]) -> list[dict]:
    """Cắt bớt chunk xếp hạng thấp cho vừa trần ngữ cảnh, giữ nguyên thứ tự.

    Phải gọi TRƯỚC khi đánh số nguồn, nếu không model được bảo "có N nguồn"
    trong khi chỉ nhìn thấy ít hơn, và số trích dẫn sẽ trỏ vào chỗ trống.
    """
    kept, used = [], 0
    for c in chunks:
        size = len(c["text"])
        if kept and used + size > MAX_CONTEXT_CHARS:
            break
        if size > MAX_CONTEXT_CHARS:
            # Chunk đầu bảng dài hơn cả trần thì cắt cụt, đừng thả nguyên: kho
            # có 35 chunk vượt 16.000 ký tự (dài nhất 116.731), gửi nguyên là
            # ~33.000 token và Groq trả 413 Request too large (trần 8.000).
            # Tạo dict mới vì chunk gốc còn dùng để hiện nguồn trên giao diện.
            c = {**c, "text": c["text"][:MAX_CONTEXT_CHARS]}
            size = MAX_CONTEXT_CHARS
        kept.append(c)
        used += size
    return kept

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-flash-latest"  # 3.6-flash free tier chỉ 20 request/NGÀY

# Model biết suy nghĩ (Gemini, gpt-oss) đốt ~1400 token lý luận cho một câu tra
# cứu đã có sẵn ngữ cảnh, gấp ~4 lần câu trả lời. "low" cắt phần lớn. Provider
# không hỗ trợ tham số này thì _call_with_retry gọi lại lần nữa, bỏ nó ra.
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")

# Groq free tier chặn theo OUTPUT TOKENS MỖI PHÚT chứ không phải số request:
# model qwen/qwen3.8-27b có OTPM limit 1000. Không đặt max_tokens thì Groq lấy
# mặc định của model (~2048) làm "expected output" và từ chối ngay cả request
# đầu tiên ("Limit 1000, Requested 1473 ... reduce max_tokens"). Đo trên bản
# deploy thật. Câu trả lời pháp lý thường 200-500 token nên 800 không cắt cụt gì.
MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "800"))

# 503 "high demand" từ Gemini rất hay gặp; chờ rồi thử lại thay vì ném cho người dùng.
RETRY_DELAYS = (2.0, 5.0)

# Giây. Groq trả lời trong ~2,2 giây (đo thật); 30 giây là trần rất rộng.
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

PROMPT_TEMPLATE = """Bạn là trợ lý pháp lý chuyên về luật Việt Nam.
Dựa vào các điều luật được đánh số sau đây, hãy trả lời câu hỏi một cách chính xác và ngắn gọn.
Chỉ trả lời dựa trên thông tin được cung cấp. Nếu không tìm thấy thông tin, hãy nói rõ.

{scope}

Trước khi viết câu trả lời, hãy tự hỏi: các điều luật ở dưới có THỰC SỰ trả lời
đúng câu hỏi không, hay chỉ cùng chủ đề? Nếu chúng chỉ cùng chủ đề mà không
chứa câu trả lời, hãy trả lời theo đúng khuôn sau:

{marker}
<một hoặc hai câu giải thích các điều luật được cung cấp không chứa thông tin
nào, và loại văn bản nào mới chứa nó>

Tuyệt đối KHÔNG ghép các điều luật gần chủ đề lại để tạo ra một câu trả lời
nghe có vẻ đúng.

Khi nói loại văn bản nào mới chứa câu trả lời, chỉ nêu LOẠI (ví dụ "nghị định
xử phạt vi phạm hành chính trong lĩnh vực giao thông"). Chỉ được nêu số hiệu
cụ thể nếu số hiệu đó xuất hiện NGUYÊN VĂN trong các nguồn ở dưới; số hiệu tự
nhớ ra (kiểu "Nghị định 123/2021/NĐ-CP") thì tuyệt đối không nêu, vì nêu sai
còn tệ hơn không nêu.

QUY TẮC TRÍCH DẪN - bắt buộc tuân thủ:
- Sau mỗi mệnh đề, ghi số nguồn trong ngoặc vuông, ví dụ [1] hoặc [3].
- Chỉ được dùng số từ 1 đến {n}. Tuyệt đối không ghi số nằm ngoài khoảng này.
- Nếu một mệnh đề không dựa trên nguồn nào, không ghi trích dẫn cho mệnh đề đó.

ĐỊNH DẠNG:
- Viết thành đoạn văn hoặc gạch đầu dòng "- ". Không dùng tiêu đề markdown (##).
- Chỉ dùng **in đậm** cho thuật ngữ then chốt.

--- CÁC ĐIỀU LUẬT LIÊN QUAN ---
{context}
--- KẾT THÚC ---

Câu hỏi: {question}

Câu trả lời:"""


_TYPE_NAMES = {
    "law": "LUẬT", "code": "BỘ LUẬT", "constitution": "HIẾN PHÁP",
    "decree": "NGHỊ ĐỊNH", "circular": "THÔNG TƯ", "decision": "QUYẾT ĐỊNH",
    "resolution": "NGHỊ QUYẾT", "ordinance": "PHÁP LỆNH",
    "directive": "CHỈ THỊ", "consolidated": "VĂN BẢN HỢP NHẤT",
}

# Chỉ hai loại này đáng nói khi thiếu: mức phạt hành chính, lệ phí, biểu phí và
# thủ tục chi tiết đều nằm ở đây, và đó là phần lớn câu hỏi đời thường.
_NOTABLE_TYPES = {"decree": "nghị định", "circular": "thông tư"}


def scope_paragraph(law_types) -> str:
    """Mô tả phạm vi kho, SINH TỪ law_type có thật chứ không viết cứng.

    Bản viết cứng cũ ("Kho KHÔNG có nghị định") đúng khi kho chỉ có dữ liệu
    HuggingFace, nhưng thành lời nói dối ngay khi crawl được nghị định đầu
    tiên - và model sẽ trả KHÔNG_TÌM_THẤY cho đúng câu nó vừa trả lời được.
    Chưa biết kho có gì thì không nói gì, thà thiếu còn hơn nói sai.
    """
    if not law_types:
        return ""
    have = ", ".join(_TYPE_NAMES.get(t, t.upper()) for t in sorted(law_types))
    lines = ["PHẠM VI KHO DỮ LIỆU - đọc kỹ trước khi trả lời:",
             f"Kho chứa các loại văn bản: {have}."]
    absent = [name for key, name in _NOTABLE_TYPES.items() if key not in law_types]
    if absent:
        lines.append(
            f"Kho KHÔNG có {' và '.join(absent)}. Câu hỏi về MỨC PHẠT HÀNH CHÍNH "
            "cụ thể, lệ phí, biểu phí hay thủ tục chi tiết thường nằm ở đó nên "
            "KHÔNG trả lời được từ kho này.")
    return "\n".join(lines)


def build_prompt(question: str, chunks: list[dict], law_types=None) -> str:
    context = "\n\n".join(
        f"[{i}] {c['title']}\n{c['text']}" for i, c in enumerate(chunks, start=1)
    )
    return PROMPT_TEMPLATE.format(
        context=context, question=question, n=len(chunks),
        marker=NO_ANSWER_MARKER, scope=scope_paragraph(law_types),
    )


# Số lượt cũ tối đa đưa vào hội thoại. Ba cặp hỏi-đáp đủ để hiểu "còn ô tô thì
# sao", mà vẫn giữ phần nhập đầu vào nhỏ: mỗi lượt cũ là token phải trả tiền và
# phải nằm trong hạn mức token mỗi phút của nhà cung cấp.
MAX_HISTORY_TURNS = 6
# Câu trả lời cũ chỉ cần đủ để model nhớ đang nói về chuyện gì, không cần
# nguyên văn. Cắt ngắn để một cuộc dài không phình phần nhập đầu vào vô hạn.
MAX_HISTORY_CHARS = 600


def build_messages(prompt: str, history=None) -> list[dict]:
    """Ghép các lượt cũ thành hội thoại, lượt hiện tại là tin nhắn cuối.

    Câu trả lời cũ bị bóc số dẫn nguồn: [3] ở lượt trước trỏ tới cách đánh số
    nguồn của lượt trước, mà lượt này truy xuất lại nên [3] đã là điều luật
    khác. Để nguyên thì model bê số cũ sang câu mới và trích dẫn trỏ sai điều.
    """
    messages = []
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if role == "assistant":
            content = strip_citations(content).strip()
        messages.append({"role": role, "content": content[:MAX_HISTORY_CHARS]})
    messages.append({"role": "user", "content": prompt})
    return messages


CONDENSE_MAX_TOKENS = int(os.getenv("LLM_CONDENSE_MAX_TOKENS", "300"))

CONDENSE_TEMPLATE = """Đoạn hội thoại hỏi đáp pháp luật:
{doan_hoi_thoai}

Câu hỏi mới nhất: {cau_hoi}

Viết lại câu hỏi mới nhất thành MỘT câu hỏi đầy đủ nghĩa khi đứng một mình,
thay các từ như "nó", "còn ... thì sao" bằng đối tượng cụ thể đang được nói
tới. Giữ nguyên thuật ngữ pháp lý. Chỉ in ra câu hỏi, không giải thích gì thêm.
"""


def _answer_text(response) -> str:
    """Nội dung câu trả lời sau khi bỏ phần suy luận, rỗng nếu model không viết gì."""
    raw = response.choices[0].message.content or ""
    return _THINK_RE.sub("", raw).strip()


def _is_overloaded(exc: Exception) -> bool:
    s = str(exc)
    return any(k in s for k in ("503", "UNAVAILABLE", "high demand", "overloaded"))


def _rejects_reasoning_effort(exc: Exception) -> bool:
    s = str(exc).lower()
    return "reasoning_effort" in s or "reasoning effort" in s


class Generator:
    def __init__(self, api_key: str = None, model_name: str = None, base_url: str = None,
                 law_types=None):
        # law_types do người dựng Generator truyền vào (đọc từ corpus_meta.json),
        # vì Generator không biết gì về vectorstore.
        self.law_types = law_types
        self.model_name = model_name or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(
            api_key=api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY"),
            base_url=base_url or os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
            # Mặc định của SDK là 600 giây và 2 lần thử lại. Trên Cloud Run
            # scale-to-zero, một cuộc gọi treo giữ instance sống và bị tính tiền
            # tới 30 phút. Đo thật: Groq trả lời trong 2,2 giây, nên 30 giây đã
            # là rất rộng rãi. _call_with_retry đã lo phần thử lại khi 503 nên
            # để SDK thử lại thêm chỉ nhân đôi thời gian chờ.
            timeout=LLM_TIMEOUT,
            max_retries=1,
        )

    def _create(self, messages, with_reasoning: bool):
        kwargs = {"model": self.model_name, "messages": messages,
                  "max_tokens": MAX_OUTPUT_TOKENS}
        if with_reasoning and REASONING_EFFORT:
            kwargs["reasoning_effort"] = REASONING_EFFORT
        return self.client.chat.completions.create(**kwargs)

    def _call_with_retry(self, messages):
        for delay in RETRY_DELAYS + (None,):
            try:
                return self._create(messages, with_reasoning=True)
            except Exception as exc:
                if _rejects_reasoning_effort(exc):
                    return self._create(messages, with_reasoning=False)
                if delay is None or not _is_overloaded(exc):
                    raise
                time.sleep(delay)

    def condense(self, question: str, history) -> str:
        """Viết lại câu hỏi nối tiếp thành một câu hỏi tự đứng được.

        Chỉ dùng cho câu CỤT, không bao giờ đụng tới câu vốn đã đủ nghĩa. Phân
        biệt này quan trọng: dự án từng đo việc cho model viết lại câu hỏi đã
        đầy đủ và Recall@5 tụt từ 0,864 xuống 0,545, vì model thêm chữ thừa và
        làm loãng từ khoá pháp lý. Ở đây việc ngược lại - câu đang thiếu nghĩa,
        thêm nghĩa vào là đúng.

        Vì sao cần: "Vượt đèn đỏ xe máy phạt bao nhiêu?" rồi "còn ô tô thì
        sao?" nếu chỉ ghép chuỗi thì cụm "xe máy" vẫn kéo kho trả về Điều 7
        (xe máy) và Điều 6 (ô tô) không lọt nổi top 5. Viết lại thành "Ô tô
        vượt đèn đỏ bị phạt bao nhiêu tiền?" thì Điều 6 lên hạng.
        """
        doan = "\n".join(
            ("Người hỏi: " if t.get("role") == "user" else "Trả lời: ")
            + strip_citations(t.get("content", "")).strip()[:400]
            for t in (history or [])[-MAX_HISTORY_TURNS:]
        )
        prompt = CONDENSE_TEMPLATE.format(doan_hoi_thoai=doan, cau_hoi=question)
        res = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            # Một câu hỏi thì ngắn. Trần thấp giữ độ trễ và tiền ở mức không
            # đáng kể so với lượt sinh câu trả lời chính.
            max_tokens=CONDENSE_MAX_TOKENS,
        )
        out = _THINK_RE.sub("", res.choices[0].message.content or "").strip()
        # Model hay bọc câu hỏi trong ngoặc kép hoặc thêm nhãn.
        return out.strip('"\u201c\u201d\'').split("\n")[0].strip()

    def generate(self, question: str, chunks: list[dict], history=None) -> dict:
        prompt = build_prompt(question, chunks, self.law_types)
        messages = build_messages(prompt, history)
        response = self._call_with_retry(messages)
        answer = _answer_text(response)

        if not answer:
            # Model tiêu hết trần token vào phần suy luận rồi không còn chỗ
            # viết câu trả lời, nên nội dung trả về rỗng. Bắt được trên bản
            # chạy thật, đúng ở câu hỏi nối tiếp: có lịch sử hội thoại thì nó
            # suy luận dài hơn nên chạm trần thường xuyên hơn.
            #
            # Thử lại một lần với phần suy luận tắt đi, dồn cả trần token cho
            # câu trả lời. Không nâng MAX_OUTPUT_TOKENS vì hạn mức token mỗi
            # phút của Groq đã từng chặn ở đúng chỗ này (Limit 1000).
            try:
                answer = _answer_text(self._create(messages, with_reasoning=False))
            except Exception:
                logger.exception("gọi lại không-suy-luận cũng hỏng")

        if not answer:
            answer = "Hệ thống không tạo được câu trả lời cho câu hỏi này."

        answered = not answer.lstrip().upper().startswith(NO_ANSWER_MARKER)
        if not answered:
            answer = answer.lstrip()[len(NO_ANSWER_MARKER):].lstrip(" :\n-").strip()
            return {"answer": answer, "sources": [], "citations": [],
                    "chunks_used": chunks, "answered": False}

        citations = []
        for raw in _CITE_RE.findall(answer):
            n = int(raw)
            if 1 <= n <= len(chunks) and n not in citations:
                citations.append(n)
        sources = list({c["title"] for c in chunks})
        return {
            "answer": answer,
            "sources": sources,
            "citations": citations,
            "chunks_used": chunks,
            "answered": True,
        }

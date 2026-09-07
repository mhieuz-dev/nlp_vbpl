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
import os
import re
import time

from openai import OpenAI

_CITE_RE = re.compile(r"\[(\d+)\]")

# Model suy nghĩ (qwen3.6 trên Groq) rò khối lý luận tiếng Anh vào câu trả lời.
# Bỏ cả trường hợp thẻ mở không có thẻ đóng (phản hồi bị cắt giữa chừng).
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)

# Kho chỉ có luật / bộ luật / hiến pháp. Đo thật trên 48.803 chunk: 0 nghị định,
# 0 thông tư. Mức phạt hành chính (vượt đèn đỏ, nồng độ cồn, lệ phí...) nằm trong
# NGHỊ ĐỊNH nên không thể trả lời được. Ngưỡng điểm KHÔNG chặn được: điểm của câu
# trả lời được (0,861-0,890) chồng lấn câu không trả lời được (0,843-0,864).
# Nên để chính model phán đoán, đánh dấu bằng một dòng máy đọc được.
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

# 503 "high demand" từ Gemini rất hay gặp; chờ rồi thử lại thay vì ném cho người dùng.
RETRY_DELAYS = (2.0, 5.0)

PROMPT_TEMPLATE = """Bạn là trợ lý pháp lý chuyên về luật Việt Nam.
Dựa vào các điều luật được đánh số sau đây, hãy trả lời câu hỏi một cách chính xác và ngắn gọn.
Chỉ trả lời dựa trên thông tin được cung cấp. Nếu không tìm thấy thông tin, hãy nói rõ.

PHẠM VI KHO DỮ LIỆU - đọc kỹ trước khi trả lời:
Kho chỉ chứa LUẬT, BỘ LUẬT và HIẾN PHÁP. Kho KHÔNG có nghị định, thông tư,
quyết định. Do đó các câu hỏi về MỨC PHẠT HÀNH CHÍNH cụ thể (vượt đèn đỏ,
nồng độ cồn, không đội mũ bảo hiểm...), lệ phí, biểu phí, thủ tục chi tiết
thường KHÔNG trả lời được, vì chúng nằm trong nghị định.

Trước khi viết câu trả lời, hãy tự hỏi: các điều luật ở dưới có THỰC SỰ trả lời
đúng câu hỏi không, hay chỉ cùng chủ đề? Nếu chúng chỉ cùng chủ đề mà không
chứa câu trả lời, hãy trả lời theo đúng khuôn sau:

{marker}
<một hoặc hai câu giải thích các điều luật được cung cấp không chứa thông tin
nào, và loại văn bản nào mới chứa nó>

Tuyệt đối KHÔNG ghép các điều luật gần chủ đề lại để tạo ra một câu trả lời
nghe có vẻ đúng.

Khi nói loại văn bản nào mới chứa câu trả lời, chỉ nêu LOẠI (ví dụ "nghị định
xử phạt vi phạm hành chính trong lĩnh vực giao thông"). TUYỆT ĐỐI không nêu số
hiệu cụ thể (kiểu "Nghị định 123/2021/NĐ-CP") vì số hiệu đó không có trong kho
và nêu sai còn tệ hơn không nêu.

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


def _is_overloaded(exc: Exception) -> bool:
    s = str(exc)
    return any(k in s for k in ("503", "UNAVAILABLE", "high demand", "overloaded"))


def _rejects_reasoning_effort(exc: Exception) -> bool:
    s = str(exc).lower()
    return "reasoning_effort" in s or "reasoning effort" in s


class Generator:
    def __init__(self, api_key: str = None, model_name: str = None, base_url: str = None):
        self.model_name = model_name or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(
            api_key=api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY"),
            base_url=base_url or os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
        )

    def _create(self, messages, with_reasoning: bool):
        kwargs = {"model": self.model_name, "messages": messages}
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

    def generate(self, question: str, chunks: list[dict]) -> dict:
        context = "\n\n".join(
            f"[{i}] {c['title']}\n{c['text']}" for i, c in enumerate(chunks, start=1)
        )
        prompt = PROMPT_TEMPLATE.format(
            context=context, question=question, n=len(chunks), marker=NO_ANSWER_MARKER
        )
        response = self._call_with_retry([{"role": "user", "content": prompt}])

        raw = response.choices[0].message.content or ""
        answer = _THINK_RE.sub("", raw).strip()
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

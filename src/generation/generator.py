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

QUY TẮC TRÍCH DẪN - bắt buộc tuân thủ:
- Sau mỗi mệnh đề, ghi số nguồn trong ngoặc vuông, ví dụ [1] hoặc [3].
- Chỉ được dùng số từ 1 đến {n}. Tuyệt đối không ghi số nằm ngoài khoảng này.
- Nếu một mệnh đề không dựa trên nguồn nào, không ghi trích dẫn cho mệnh đề đó.

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
        prompt = PROMPT_TEMPLATE.format(context=context, question=question, n=len(chunks))
        response = self._call_with_retry([{"role": "user", "content": prompt}])

        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = "Hệ thống không tạo được câu trả lời cho câu hỏi này."

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
        }

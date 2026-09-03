import re

from google import genai
from google.genai import types

_CITE_RE = re.compile(r"\[(\d+)\]")

PROMPT_TEMPLATE = """Bạn là trợ lý pháp lý chuyên về luật Việt Nam.
Dựa vào các điều luật được đánh số sau đây, hãy trả lời câu hỏi một cách chính xác và ngắn gọn.
Chỉ trả lời dựa trên thông tin được cung cấp. Nếu không tìm thấy thông tin, hãy nói rõ.

QUY TẮC TRÍCH DẪN — bắt buộc tuân thủ:
- Sau mỗi mệnh đề, ghi số nguồn trong ngoặc vuông, ví dụ [1] hoặc [3].
- Chỉ được dùng số từ 1 đến {n}. Tuyệt đối không ghi số nằm ngoài khoảng này.
- Nếu một mệnh đề không dựa trên nguồn nào, không ghi trích dẫn cho mệnh đề đó.

--- CÁC ĐIỀU LUẬT LIÊN QUAN ---
{context}
--- KẾT THÚC ---

Câu hỏi: {question}

Câu trả lời:"""


class Generator:
    def __init__(self, api_key: str, model_name: str = "gemini-3.6-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate(self, question: str, chunks: list[dict]) -> dict:
        context = "\n\n".join([
            f"[{i}] {c['title']}\n{c['text']}"
            for i, c in enumerate(chunks, start=1)
        ])
        prompt = PROMPT_TEMPLATE.format(
            context=context, question=question, n=len(chunks)
        )
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        answer = response.text or "Hệ thống không tạo được câu trả lời cho câu hỏi này."
        citations = []
        for raw in _CITE_RE.findall(answer or ""):
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

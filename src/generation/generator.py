from google import genai
from google.genai import types

PROMPT_TEMPLATE = """Bạn là trợ lý pháp lý chuyên về luật Việt Nam.
Dựa vào các điều luật sau đây, hãy trả lời câu hỏi một cách chính xác và ngắn gọn.
Chỉ trả lời dựa trên thông tin được cung cấp. Nếu không tìm thấy thông tin, hãy nói rõ.

--- CÁC ĐIỀU LUẬT LIÊN QUAN ---
{context}
--- KẾT THÚC ---

Câu hỏi: {question}

Câu trả lời:"""

class Generator:
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate(self, question: str, chunks: list[dict]) -> dict:
        context = "\n\n".join([
            f"[{c['title']}]\n{c['text']}" for c in chunks
        ])
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        sources = list({c["title"] for c in chunks})
        return {
            "answer": response.text,
            "sources": sources,
            "chunks_used": chunks,
        }

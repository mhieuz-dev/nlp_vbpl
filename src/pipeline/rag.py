from src.vectorstore.store import VectorStore
from src.generation.generator import Generator

class RAGPipeline:
    # top_k=15, nâng từ 10 sau khi đo lại trên kho hiện tại.
    #
    # Trên bộ 22 câu eval thì Recall chững từ k=10 (0,8636 ở cả k=10/15/20), nên
    # con số đó KHÔNG phải lý do nâng. Lý do là một ca thật ngoài bộ eval: hỏi
    # "Ô tô vượt đèn đỏ bị phạt bao nhiêu?" thì chunk đúng (Điều 6 khoản 9, mức
    # 18-20 triệu) nằm ở HẠNG 13 - ngay ngoài ngưỡng 10 - nên hệ thống trả lời
    # là không tìm thấy. Khoảng cách chữ nghĩa: người hỏi nói "vượt đèn đỏ",
    # luật viết "không chấp hành hiệu lệnh của đèn tín hiệu giao thông".
    #
    # Nâng lên 15 không làm prompt phình: trần 16.000 ký tự của fit_to_context
    # mới là ràng buộc thật, đo được là 14 chunk sống sót (14.768 ký tự) ở cả
    # k=15 lẫn k=20. Nên 20 không hơn 15, chỉ tốn thêm công tìm.
    def __init__(self, store: VectorStore, generator: Generator, top_k: int = 15):
        self.store = store
        self.generator = generator
        self.top_k = top_k

    def ask(self, question: str) -> dict:
        chunks = self.store.query(question, top_k=self.top_k)
        result = self.generator.generate(question, chunks)
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "retrieved_chunks": chunks,
        }

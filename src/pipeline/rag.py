from src.vectorstore.store import VectorStore
from src.generation.generator import Generator, fit_to_context
from src.pipeline.followup import retrieval_query
from src.pipeline.synonyms import expand_query


def build_store(embedder) -> VectorStore:
    """Kho dùng chung cho server và bộ đánh giá, để hai bên tìm theo cùng một cách.

    article_lookup: câu hỏi nêu đích danh "Điều N" thì dense gần như không tìm
    được (đo thật: Điều 630 không lọt cả top-30). Bật lên, Recall@5 0.773 ->
    0.864, MRR 0.551 -> 0.712.
    """
    return VectorStore(embedder=embedder, article_lookup=True)


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
    #
    # expand_terms chỉ để bộ đánh giá đo được tác dụng của từ điển thuật ngữ;
    # app luôn chạy với giá trị mặc định.
    def __init__(self, store: VectorStore, generator: Generator, top_k: int = 15,
                 expand_terms: bool = True):
        self.store = store
        self.generator = generator
        self.top_k = top_k
        self.expand_terms = expand_terms

    def search_query(self, question: str, history=None) -> str:
        """Câu đem đi TÌM, khác câu gửi cho model ĐỌC.

        Hai bước, đúng thứ tự này: làm câu hỏi đủ nghĩa trước (câu nối tiếp cần
        ngữ cảnh), rồi mới nối thuật ngữ luật vào. Đổi thứ tự thì câu cụt kiểu
        "còn ô tô thì sao?" chưa có chữ nào để từ điển bắt.
        """
        truy_van = retrieval_query(question, history,
                                   condense=getattr(self.generator, "condense", None))
        return expand_query(truy_van) if self.expand_terms else truy_van

    def retrieve(self, question: str, history=None, fit: bool = True) -> list[dict]:
        """Đường truy xuất duy nhất của hệ thống: server, ask() và bộ đánh giá đều đi qua đây.

        fit=True cắt cho vừa trần ngữ cảnh, đúng những gì model được đọc. Phải
        cắt TRƯỚC khi đánh số nguồn, để số nguồn model thấy khớp với số nguồn
        hiển thị trên giao diện. fit=False chỉ để bộ đánh giá đo hạng trước khi cắt.
        """
        chunks = self.store.query(self.search_query(question, history), top_k=self.top_k)
        return fit_to_context(chunks) if fit else chunks

    def ask(self, question: str, history=None) -> dict:
        chunks = self.retrieve(question, history)
        result = self.generator.generate(question, chunks, history=history)
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "retrieved_chunks": chunks,
        }

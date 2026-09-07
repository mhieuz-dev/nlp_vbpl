import re
import unicodedata

import chromadb
from src.embeddings.embedder import Embedder
from src.vectorstore.article_index import ArticleIndex, parse_article_ref

_DIEU_RE = re.compile(r"^\s*Điều\s+(\d+)")

# Kho nạp từ UTS_VLC chứa mỗi bộ luật khoảng 3 lần dưới 3 cách viết tên khác
# nhau, nội dung chỉ lệch ở khoảng trắng và dấu chấm. Không khử thì top-5 bị
# các bản sao chiếm hết chỗ (đo thật: top-10 chỉ còn 4 điều khác nhau).
DEDUP_OVERFETCH = 4

# Ba trường này chỉ có ở văn bản crawl từ Công báo. 48.803 chunk nạp từ
# HuggingFace không có, nên mọi chỗ đọc đều phải .get(..., "").
OPTIONAL_META = ("issue_date", "source_url", "doc_number")


def _prefer(new: dict, old: dict) -> bool:
    """Hai chunk trùng khoá so trùng thì có nên thay bản cũ bằng bản mới không.

    Công báo là kho CÔNG BỐ, không có trường "còn hiệu lực": NĐ 100/2019 và
    NĐ 168/2024 thay thế nó cùng nằm trong kho và giống nhau gần hết 160 ký tự
    đầu. Không phân xử theo ngày thì bản nào sống sót là ngẫu nhiên, và người
    hỏi có thể nhận đúng mức phạt của văn bản đã bị bãi bỏ. Ngày rỗng thua mọi
    ngày thật, nên chunk cũ không đá được chunk có ngày ra ngoài.
    """
    return new.get("issue_date", "") > old.get("issue_date", "")


def _dedup_key(text: str) -> str:
    """Khoá so trùng: bỏ dấu tiếng Việt, bỏ ký tự không phải chữ-số, lấy 160 ký tự đầu."""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:160]

class VectorStore:
    def __init__(self, embedder: Embedder, collection_name: str = "vn_legal",
                 persist_dir: str = "./data/chroma_db", article_lookup: bool = False):
        self.embedder = embedder
        # Chỉ mục tra theo số điều dựng lười ở truy vấn đầu tiên có nêu "Điều N",
        # để test và các đường dùng khác không phải trả giá dựng chỉ mục.
        self.article_lookup = article_lookup
        self._article_index = None
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    BATCH_SIZE = 500

    def insert(self, chunks: list[dict]) -> None:
        for i in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[i:i + self.BATCH_SIZE]
            texts = [c["text"] for c in batch]
            embeddings = self.embedder.embed(texts)
            self.collection.upsert(
                ids=[c["chunk_id"] for c in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "doc_id": c["doc_id"],
                    "title": c["title"],
                    "law_type": c["law_type"],
                    **{k: c.get(k, "") for k in OPTIONAL_META},
                } for c in batch],
            )
            print(f"  Indexed {min(i + self.BATCH_SIZE, len(chunks))}/{len(chunks)} chunks...")

    def _to_chunk(self, cid, doc, meta, score):
        m = _DIEU_RE.match(doc)
        return {
            "chunk_id": cid,
            "article": int(m.group(1)) if m else None,
            "text": doc,
            "title": meta["title"],
            "law_type": meta["law_type"],
            "score": score,
            **{k: meta.get(k, "") for k in OPTIONAL_META},
        }

    def delete_doc(self, doc_id: str) -> int:
        """Xoá mọi chunk của một văn bản, trả về số chunk đã xoá.

        Phải gọi trước khi nạp lại: upsert chỉ ghi đè theo chunk_id, nên lần
        crawl sau ra ít chunk hơn thì phần dư của lần trước nằm lại vĩnh viễn.
        """
        ids = self.collection.get(where={"doc_id": doc_id})["ids"]
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    def _lookup_by_article(self, query_text: str) -> list[dict]:
        """Chunk của điều luật được nêu đích danh trong câu hỏi, nếu có."""
        ref = parse_article_ref(query_text)
        if not ref:
            return []
        if self._article_index is None:
            self._article_index = ArticleIndex(self.collection)
        ids = self._article_index.find(*ref)
        if not ids:
            return []
        got = self.collection.get(ids=ids[:20], include=["documents", "metadatas"])
        return [
            self._to_chunk(cid, doc, meta, 1.0)
            for cid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"])
        ]

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        query_embedding = self.embedder.embed_query(query_text)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * DEDUP_OVERFETCH,
            include=["documents", "metadatas", "distances"],
        )
        output = []
        seen = {}  # khoá so trùng -> vị trí trong output

        def take(chunk) -> bool:
            """Nhận một chunk, trả True khi output đã đủ top_k."""
            key = _dedup_key(chunk["text"])
            pos = seen.get(key)
            if pos is None:
                seen[key] = len(output)
                output.append(chunk)
            elif _prefer(chunk, output[pos]):
                output[pos] = chunk
            return len(output) == top_k

        if self.article_lookup:
            for chunk in self._lookup_by_article(query_text):
                if take(chunk):
                    return output
        for cid, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            if take(self._to_chunk(cid, doc, meta, round(1 - dist, 4))):
                break
        return output

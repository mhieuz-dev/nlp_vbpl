import json
import logging
import threading
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.embeddings.embedder import Embedder
from src.generation.generator import Generator, fit_to_context
from src.ingestion.corpus_meta import read_meta
from src.vectorstore.bootstrap import ensure_corpus
from src.pipeline.rag import RAGPipeline
from src.vectorstore.store import VectorStore

load_dotenv()

logger = logging.getLogger(__name__)

# None = để read_meta tự chọn (data/corpus_meta.json trước, rồi gốc repo).
# Test thay bằng monkeypatch khi cần một đường cụ thể.
CORPUS_META_PATH = None

# Nạp model + kho mất ~2 phút trên Cloud Run (tải tarball 340 MB + dựng e5-base
# 1,5 GB). uvicorn phải mở cổng ngay để trang tĩnh và /healthz phục vụ được,
# nên việc dựng pipeline chạy ở một luồng nền do lifespan khởi động. Bốn biến
# dưới là máy trạng thái của luồng đó; _lock chặn hai request đồng thời cùng
# dựng SentenceTransformer (2 × 1,5 GB = chết OOM trong container 4 GiB).
_pipeline = None
_load_state = "idle"  # idle -> loading -> ready | failed
_load_error = None
_load_started_at = None
_lock = threading.Lock()


def _build_pipeline() -> RAGPipeline:
    """Dựng pipeline thật. Chỉ gọi trong _warm_load hoặc get_pipeline, dưới _lock."""
    ensure_corpus()
    embedder = Embedder()
    # article_lookup: câu hỏi nêu đích danh "Điều N" thì dense gần như không tìm
    # được (đo thật: Điều 630 không lọt cả top-30). Bật lên, Recall@5 0.773 ->
    # 0.864, MRR 0.551 -> 0.712.
    store = VectorStore(embedder=embedder, article_lookup=True)
    # Phạm vi kho lấy từ corpus_meta.json (do refresh_corpus.py ghi) chứ không
    # quét lại 49.063 chunk lúc khởi động. Chưa có file thì scope_paragraph()
    # im lặng, không đưa ra khẳng định nào.
    meta = read_meta(CORPUS_META_PATH)
    law_types = set(meta["law_types"]) if meta else None
    generator = Generator(law_types=law_types)  # đọc LLM_* từ môi trường
    return RAGPipeline(store=store, generator=generator)


def _warm_load() -> None:
    """Dựng pipeline ở luồng nền. Ghi trạng thái để get_pipeline / healthz đọc."""
    global _pipeline, _load_state, _load_error, _load_started_at
    with _lock:
        if _pipeline is not None or _load_state == "loading":
            return
        _load_state = "loading"
        _load_started_at = time.monotonic()
    try:
        pipe = _build_pipeline()
    except Exception as exc:  # noqa: BLE001 - ghi lại mọi lỗi để healthz báo
        logger.exception("Dựng pipeline thất bại")
        with _lock:
            _load_state, _load_error = "failed", str(exc)
        return
    with _lock:
        _pipeline, _load_state, _load_error = pipe, "ready", None


def get_pipeline() -> RAGPipeline:
    """Dependency cho /api/ask*. Trả pipeline khi sẵn sàng, 503 khi chưa.

    Khách vào lúc đang nạp nhận 503 CÓ CẤU TRÚC ({"status": "warming",
    "elapsed_s": N}) để giao diện hiện "đang khởi động" và tự thử lại, thay vì
    để EventSource treo rồi báo "mất kết nối" - một lời nói dối.
    """
    if _pipeline is not None:
        return _pipeline
    if _load_state == "failed":
        raise HTTPException(status_code=503, detail={
            "status": "failed",
            "message": "Máy chủ không nạp được kho dữ liệu. Xem log để biết chi tiết.",
        })
    if _load_state == "loading":
        elapsed = int(time.monotonic() - (_load_started_at or time.monotonic()))
        raise HTTPException(status_code=503, detail={
            "status": "warming", "elapsed_s": elapsed,
            "message": "Máy chủ đang khởi động, thường mất khoảng 60-120 giây.",
        })
    # state == "idle": lifespan chưa chạy luồng nền (chạy trực tiếp, không qua
    # uvicorn có lifespan). Dựng đồng bộ dưới lock.
    _warm_load()
    if _pipeline is None:
        raise HTTPException(status_code=503, detail={
            "status": "failed",
            "message": "Máy chủ không nạp được kho dữ liệu.",
        })
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động luồng nền dựng pipeline, rồi cho uvicorn bind ngay.

    Bỏ qua khi test đã override get_pipeline để không nạp model thật.
    """
    if get_pipeline not in app.dependency_overrides:
        threading.Thread(target=_warm_load, name="warm-load", daemon=True).start()
    yield


app = FastAPI(title="luật.ai", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@app.get("/healthz")
def healthz():
    """Cloud Run startup probe trỏ vào đây. alive=true ngay khi cổng mở;
    ready=true khi pipeline đã dựng xong."""
    return {
        "alive": True,
        "ready": _pipeline is not None,
        "state": _load_state,
        "elapsed_s": (int(time.monotonic() - _load_started_at)
                      if _load_started_at and _pipeline is None else None),
    }


def number_chunks(chunks: list[dict]) -> list[dict]:
    """Gắn số thứ tự 1..n để khớp với trích dẫn [n] trong câu trả lời."""
    return [
        {
            "n": i,
            "chunk_id": c.get("chunk_id"),
            "article": c.get("article"),
            "title": c["title"],
            "law_type": c["law_type"],
            "score": c["score"],
            "text": c["text"],
        }
        for i, c in enumerate(chunks, start=1)
    ]


def run_query_events(pipeline, question: str):
    """Chạy truy vấn, sinh (event, data) theo đúng thời điểm xảy ra.

    Ba bước đo được thật: retrieve (embed + tìm kiếm), generate, cite.
    Sự kiện cuối luôn là ("done", payload) — payload giống hệt POST /api/ask.
    """
    t0 = time.perf_counter()
    chunks = pipeline.store.query(question, top_k=pipeline.top_k)
    # Cắt cho vừa trần ngữ cảnh TRƯỚC khi đánh số, để số nguồn model thấy khớp
    # với số nguồn hiển thị trên giao diện.
    chunks = fit_to_context(chunks)
    t1 = time.perf_counter()
    retrieve_ms = int((t1 - t0) * 1000)
    yield "step", {"step": "retrieve", "ms": retrieve_ms, "found": len(chunks)}

    numbered = number_chunks(chunks)
    yield "chunks", {"chunks": numbered}

    result = pipeline.generator.generate(question, chunks)
    t2 = time.perf_counter()
    generate_ms = int((t2 - t1) * 1000)
    yield "step", {"step": "generate", "ms": generate_ms}

    citations = result.get("citations", [])
    yield "step", {"step": "cite", "ms": 0, "count": len(citations)}

    yield "done", {
        "answer": result["answer"],
        "citations": citations,
        "sources": result["sources"],
        "chunks": numbered,
        "answered": result.get("answered", True),
        "model": pipeline.generator.model_name,
        "timings": {"retrieve_ms": retrieve_ms, "generate_ms": generate_ms},
    }


def run_query(pipeline, question: str) -> dict:
    """Bọc không-stream cho POST /api/ask."""
    for event, data in run_query_events(pipeline, question):
        if event == "done":
            return data


GENERIC_ERROR = "Không gọi được mô hình sinh câu trả lời. Vui lòng thử lại."
QUOTA_ERROR = (
    "Đã dùng hết hạn mức (quota) gọi mô hình của khoá API. "
    "Thử lại ngay cũng không được cho tới khi hạn mức được cấp lại."
)


def _error_message(exc: Exception) -> str:
    """Thông điệp tiếng Việt cho người dùng, không lộ chi tiết nội bộ.

    Hết quota khác hẳn lỗi tạm thời: bảo người dùng "thử lại" là sai vì
    thử lại không giúp gì cho tới khi hạn mức được cấp lại.
    """
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return QUOTA_ERROR
    return GENERIC_ERROR


@app.post("/api/ask")
def ask(req: AskRequest, pipeline=Depends(get_pipeline)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")
    try:
        return run_query(pipeline, question)
    except Exception as exc:
        logger.exception("run_query thất bại cho /api/ask")
        return JSONResponse(
            status_code=502,
            content={"error": _error_message(exc)},
        )


@app.get("/api/corpus")
def corpus():
    """Thống kê kho cho nhãn ngày trên giao diện.

    Trả null (kèm 200) khi chưa chạy refresh lần nào - đó là trạng thái hợp lệ,
    không phải lỗi máy chủ. Giao diện tự biết giữ số mặc định.
    """
    return read_meta(CORPUS_META_PATH)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

# Cloud Run và mọi proxy dạng nginx/Envoy sẽ đệm text/event-stream nếu thiếu hai
# header này, và giao diện từng bước ("retrieve -> generate -> cite") sập thành
# một cục đứng im 2,3 giây rồi hiện hết một lượt.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.get("/api/ask/stream")
def ask_stream(q: str, pipeline=Depends(get_pipeline)):
    question = q.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Câu hỏi quá dài (tối đa 1000 ký tự).")

    def stream():
        try:
            for event, data in run_query_events(pipeline, question):
                yield _sse(event, data)
        except Exception as exc:
            logger.exception("run_query thất bại cho /api/ask/stream")
            yield _sse("error", {"error": _error_message(exc)})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers=SSE_HEADERS)


app.mount("/", StaticFiles(directory="web", html=True), name="web")

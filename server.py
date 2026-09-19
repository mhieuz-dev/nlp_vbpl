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
from src.pipeline.followup import retrieval_query
from src.pipeline.synonyms import expand_query
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


class Turn(BaseModel):
    """Một lượt cũ trong cuộc hội thoại, do trình duyệt gửi lên.

    Máy chủ KHÔNG giữ trạng thái hội thoại: lịch sử nằm ở trình duyệt người
    hỏi và đi kèm mỗi lần hỏi. Hợp với Cloud Run scale-to-zero, và không bắt
    ai gửi câu hỏi pháp luật của họ vào một cơ sở dữ liệu để người khác giữ.
    """
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # Chặn trần ngay ở cửa: lịch sử do client gửi nên không tin được độ dài.
    # Sáu lượt là ba cặp hỏi-đáp, đủ để hiểu câu nối tiếp.
    history: list[Turn] = Field(default_factory=list, max_length=6)


@app.get("/api/healthz")
def healthz():
    """Trạng thái nạp pipeline: alive=true ngay khi cổng mở, ready=true khi
    model đã dựng xong. Giao diện hỏi endpoint này để phân biệt "đang khởi
    động" với "mất kết nối".

    Đặt dưới /api/ chứ KHÔNG phải /healthz: Cloud Run chiếm dụng /healthz cho
    health check nội bộ của nó và trả 404 từ Google Frontend, request không bao
    giờ tới container. Đo thật trên bản deploy.""" 
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


def run_query_events(pipeline, question: str, history=None):
    """Chạy truy vấn, sinh (event, data) theo đúng thời điểm xảy ra.

    Ba bước đo được thật: retrieve (embed + tìm kiếm), generate, cite.
    Sự kiện cuối luôn là ("done", payload) — payload giống hệt POST /api/ask.
    """
    t0 = time.perf_counter()
    # Câu đem đi TÌM khác câu gửi cho model ĐỌC: câu nối tiếp kiểu "còn ô tô
    # thì sao" tự nó không đủ nghĩa để nhúng, phải ghép câu hỏi trước vào.
    # Hai bước, đúng thứ tự này: làm câu hỏi đủ nghĩa trước (câu nối tiếp cần
    # ngữ cảnh), rồi mới nối thuật ngữ luật vào. Đổi thứ tự thì câu cụt kiểu
    # "còn ô tô thì sao?" chưa có chữ nào để từ điển bắt.
    truy_van = retrieval_query(question, history,
                               condense=getattr(pipeline.generator, "condense", None))
    truy_van = expand_query(truy_van)
    chunks = pipeline.store.query(truy_van, top_k=pipeline.top_k)
    # Cắt cho vừa trần ngữ cảnh TRƯỚC khi đánh số, để số nguồn model thấy khớp
    # với số nguồn hiển thị trên giao diện.
    chunks = fit_to_context(chunks)
    t1 = time.perf_counter()
    retrieve_ms = int((t1 - t0) * 1000)
    yield "step", {"step": "retrieve", "ms": retrieve_ms, "found": len(chunks)}

    numbered = number_chunks(chunks)
    yield "chunks", {"chunks": numbered}

    result = pipeline.generator.generate(question, chunks, history=history)
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


def run_query(pipeline, question: str, history=None) -> dict:
    """Bọc không-stream cho POST /api/ask."""
    for event, data in run_query_events(pipeline, question, history):
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
        return run_query(pipeline, question, _as_turns(req.history))
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


def _as_turns(history) -> list[dict]:
    """Đổi các Turn đã kiểm của pydantic thành dict thuần cho lớp dưới."""
    return [{"role": h.role, "content": h.content} for h in (history or [])]


# POST chứ không GET: lịch sử hội thoại không nhét vừa query string, và một
# URL vài KB sẽ bị proxy cắt ngang một cách âm thầm. Đổi lại frontend phải đọc
# stream bằng fetch thay cho EventSource, vì EventSource chỉ biết GET.
@app.post("/api/ask/stream")
def ask_stream(req: AskRequest, pipeline=Depends(get_pipeline)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")
    history = _as_turns(req.history)

    def stream():
        try:
            for event, data in run_query_events(pipeline, question, history):
                yield _sse(event, data)
        except Exception as exc:
            logger.exception("run_query thất bại cho /api/ask/stream")
            yield _sse("error", {"error": _error_message(exc)})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers=SSE_HEADERS)


class KhongCache(StaticFiles):
    """Buộc trình duyệt hỏi lại máy chủ trước khi dùng lại file tĩnh.

    Vì sao bắt buộc: Starlette chỉ gửi ETag và Last-Modified, không gửi
    Cache-Control. Thiếu Cache-Control thì trình duyệt TỰ SUY ĐOÁN thời hạn lưu
    (thường lấy 10% khoảng thời gian từ Last-Modified) và dùng lại bản cũ mà
    không hỏi lại. Hậu quả đã gặp thật sau khi deploy bản giao diện mới: người
    dùng nhận index.html MỚI nhưng style.css và app.js CŨ - CSS cũ không có
    luật nào cho thanh lịch sử nên nó đổ thành chữ trần, còn app.js cũ đi tìm
    phần tử đã đổi tên nên hỏng ngay, màn hình chủ không chịu ẩn. Trang trông
    như bị vỡ hoàn toàn dù máy chủ phục vụ đúng file.

    "no-cache" KHÔNG phải là cấm lưu: trình duyệt vẫn giữ file, chỉ phải hỏi
    lại. Có ETag nên lần hỏi lại trả 304 rỗng, gần như không tốn gì.
    """

    def file_response(self, *args, **kwargs):
        res = super().file_response(*args, **kwargs)
        res.headers["Cache-Control"] = "no-cache"
        return res


app.mount("/", KhongCache(directory="web", html=True), name="web")

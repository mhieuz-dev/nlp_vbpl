import json
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.embeddings.embedder import Embedder
from src.generation.generator import Generator
from src.pipeline.rag import RAGPipeline
from src.vectorstore.store import VectorStore

load_dotenv()

logger = logging.getLogger(__name__)

_pipeline = None


def get_pipeline() -> RAGPipeline:
    """Khởi tạo pipeline một lần rồi tái sử dụng. Nạp model mất 30-60s."""
    global _pipeline
    if _pipeline is None:
        embedder = Embedder()
        store = VectorStore(embedder=embedder)
        generator = Generator(api_key=os.getenv("GEMINI_API_KEY"))
        _pipeline = RAGPipeline(store=store, generator=generator)
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Nạp pipeline một lần lúc khởi động thay vì trong request đầu tiên.

    Nếu nạp thất bại (thiếu API key, chưa có Chroma...) thì ghi log và vẫn cho
    server bind — `get_pipeline()` sẽ thử lại ở truy vấn kế tiếp. Bỏ qua khi test
    đã override `get_pipeline` để không bao giờ nạp model thật.
    """
    if get_pipeline not in app.dependency_overrides:
        try:
            get_pipeline()
        except Exception:
            logger.exception("Nạp pipeline lúc khởi động thất bại; sẽ thử lại ở truy vấn đầu tiên")
    yield


app = FastAPI(title="luật.ai", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


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
        "timings": {"retrieve_ms": retrieve_ms, "generate_ms": generate_ms},
    }


def run_query(pipeline, question: str) -> dict:
    """Bọc không-stream cho POST /api/ask."""
    for event, data in run_query_events(pipeline, question):
        if event == "done":
            return data


@app.post("/api/ask")
def ask(req: AskRequest, pipeline=Depends(get_pipeline)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")
    try:
        return run_query(pipeline, question)
    except Exception:
        logger.exception("run_query thất bại cho /api/ask")
        return JSONResponse(
            status_code=502,
            content={"error": "Không gọi được mô hình sinh câu trả lời. Vui lòng thử lại."},
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
        except Exception:
            logger.exception("run_query thất bại cho /api/ask/stream")
            yield _sse("error", {"error": "Không gọi được mô hình sinh câu trả lời. Vui lòng thử lại."})

    return StreamingResponse(stream(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="web", html=True), name="web")

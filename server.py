import json
import logging
import os
import time

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

app = FastAPI(title="luật.ai")

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


def run_query(pipeline, question: str, emit=None) -> dict:
    """Chạy truy vấn, phát sự kiện từng bước qua `emit` nếu có.

    Ba bước đo được thật: retrieve (embed + tìm kiếm), generate, cite.
    """
    def fire(event, data):
        if emit is not None:
            emit(event, data)

    t0 = time.perf_counter()
    chunks = pipeline.store.query(question, top_k=pipeline.top_k)
    t1 = time.perf_counter()
    retrieve_ms = int((t1 - t0) * 1000)
    fire("step", {"step": "retrieve", "ms": retrieve_ms, "found": len(chunks)})

    numbered = number_chunks(chunks)
    fire("chunks", {"chunks": numbered})

    result = pipeline.generator.generate(question, chunks)
    t2 = time.perf_counter()
    generate_ms = int((t2 - t1) * 1000)
    fire("step", {"step": "generate", "ms": generate_ms})

    citations = result.get("citations", [])
    fire("step", {"step": "cite", "ms": 0, "count": len(citations)})

    return {
        "answer": result["answer"],
        "citations": citations,
        "sources": result["sources"],
        "chunks": numbered,
        "timings": {"retrieve_ms": retrieve_ms, "generate_ms": generate_ms},
    }


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
        buffer = []
        try:
            payload = run_query(
                pipeline, question,
                emit=lambda ev, data: buffer.append(_sse(ev, data)),
            )
        except Exception:
            logger.exception("run_query thất bại cho /api/ask/stream")
            yield from buffer
            yield _sse("error", {"error": "Không gọi được mô hình sinh câu trả lời. Vui lòng thử lại."})
            return
        yield from buffer
        yield _sse("done", payload)

    return StreamingResponse(stream(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="web", html=True), name="web")

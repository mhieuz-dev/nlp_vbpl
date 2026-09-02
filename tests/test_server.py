import pytest
from fastapi.testclient import TestClient

import server
from server import app, get_pipeline


class FakePipeline:
    top_k = 5

    def __init__(self, chunks=None, answer="Trả lời [1].", raises=None):
        self._chunks = chunks if chunks is not None else [{
            "chunk_id": "0_1", "article": 122, "text": "Điều 122. Giao dịch vô hiệu.",
            "title": "Bộ luật Dân sự 2015", "law_type": "bo_luat", "score": 0.9127,
        }]
        self._answer = answer
        self._raises = raises
        self.store = self
        self.generator = self

    def query(self, question, top_k=5):
        return self._chunks

    def generate(self, question, chunks):
        if self._raises:
            raise self._raises
        return {"answer": self._answer, "sources": ["Bộ luật Dân sự 2015"],
                "citations": [1], "chunks_used": chunks}


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_ask_returns_expected_shape(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    r = client.post("/api/ask", json={"question": "Hợp đồng vô hiệu khi nào?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Trả lời [1]."
    assert body["citations"] == [1]
    assert body["chunks"][0]["n"] == 1
    assert body["chunks"][0]["article"] == 122
    assert "retrieve_ms" in body["timings"]
    assert "generate_ms" in body["timings"]


def test_ask_rejects_empty_question(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    r = client.post("/api/ask", json={"question": "   "})
    assert r.status_code == 400


def test_ask_rejects_too_long_question(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    r = client.post("/api/ask", json={"question": "x" * 1001})
    assert r.status_code == 422


def test_ask_returns_502_when_generator_fails(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline(
        raises=RuntimeError("Gemini timeout")
    )
    r = client.post("/api/ask", json={"question": "câu hỏi?"})
    assert r.status_code == 502
    assert "error" in r.json()
    assert "Gemini timeout" not in r.json()["error"]


def _parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        events.append((name, data))
    return events


def test_stream_emits_steps_then_done(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    r = client.get("/api/ask/stream", params={"q": "Hợp đồng vô hiệu khi nào?"})
    assert r.status_code == 200
    names = [n for n, _ in _parse_sse(r.text)]
    assert names[0] == "step"
    assert "chunks" in names
    assert names[-1] == "done"


def test_stream_emits_error_event_when_generator_fails(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline(
        raises=RuntimeError("Gemini timeout")
    )
    r = client.get("/api/ask/stream", params={"q": "câu hỏi?"})
    names = [n for n, _ in _parse_sse(r.text)]
    assert names[-1] == "error"


def test_stream_rejects_empty_question(client):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    r = client.get("/api/ask/stream", params={"q": "  "})
    assert r.status_code == 400

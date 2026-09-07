"""Điểm vào cho HuggingFace Space.

Vì sao có file này thay vì Dockerfile: tháng 9/2026 HF chuyển SDK `docker` sang
gói trả phí, chỉ còn `static` và `gradio` miễn phí. Nhưng tài liệu Gradio Space
cho thấy HF chạy `python app.py` như một script bình thường, nên ta tự dựng
uvicorn ở đây và phục vụ đúng ứng dụng FastAPI sẵn có - giữ nguyên frontend,
toàn bộ route API và 126 test, không phải viết lại giao diện bằng Gradio.

Gradio được gắn ở /gradio làm giao diện dự phòng tối giản, đồng thời để Space
đúng nghĩa là một Gradio Space.
"""
import os

import gradio as gr
import uvicorn

from server import app as fastapi_app


def _hoi(cau_hoi: str) -> str:
    """Giao diện dự phòng, dùng chung pipeline với /api/ask."""
    from server import get_pipeline
    return get_pipeline().ask(cau_hoi)["answer"]


demo = gr.Interface(
    fn=_hoi,
    inputs=gr.Textbox(label="Câu hỏi", placeholder="Vượt đèn đỏ bị phạt bao nhiêu tiền?"),
    outputs=gr.Markdown(label="Trả lời"),
    title="luật.ai",
    description="Giao diện tối giản. Giao diện đầy đủ ở trang chủ.",
)

# server.py mount StaticFiles ở "/" (server.py:213), mà mount đó khớp MỌI đường
# dẫn đứng sau nó trong danh sách route. gr.mount_gradio_app nối route vào cuối
# nên chúng không bao giờ tới lượt - phải đưa lên trước cái mount bắt-tất-cả.
_truoc = len(fastapi_app.router.routes)
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")
_route_gradio = app.router.routes[_truoc:]
del app.router.routes[_truoc:]
app.router.routes[:0] = _route_gradio

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))

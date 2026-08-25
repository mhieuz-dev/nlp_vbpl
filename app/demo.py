import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from dotenv import load_dotenv
from src.embeddings.embedder import Embedder
from src.vectorstore.store import VectorStore
from src.generation.generator import Generator
from src.pipeline.rag import RAGPipeline

load_dotenv()

print("Loading models...")
embedder = Embedder()
store = VectorStore(embedder=embedder)
generator = Generator(api_key=os.getenv("GEMINI_API_KEY"))
pipeline = RAGPipeline(store=store, generator=generator)
print("Ready!")

def answer_question(question: str):
    if not question.strip():
        return "Vui lòng nhập câu hỏi.", "", ""

    result = pipeline.ask(question)
    sources_text = "\n".join([f"- {s}" for s in result["sources"]])

    chunks_md = ""
    for i, chunk in enumerate(result["retrieved_chunks"], 1):
        chunks_md += f"**[{i}] {chunk['title']}** (score: {chunk['score']})\n\n{chunk['text']}\n\n---\n\n"

    return result["answer"], sources_text, chunks_md

with gr.Blocks(title="VN Legal RAG QA", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# ⚖️ Hỏi đáp Pháp luật Việt Nam")
    gr.Markdown("Nhập câu hỏi về luật — hệ thống tìm điều luật liên quan và trả lời có trích dẫn nguồn.")

    with gr.Row():
        with gr.Column(scale=2):
            question_input = gr.Textbox(
                label="Câu hỏi của bạn",
                placeholder="Ví dụ: Hợp đồng vô hiệu khi nào?",
                lines=2,
            )
            submit_btn = gr.Button("Hỏi", variant="primary")
            answer_output = gr.Textbox(label="Câu trả lời", lines=6, interactive=False)
            sources_output = gr.Textbox(label="Nguồn luật được dùng", lines=3, interactive=False)

        with gr.Column(scale=1):
            chunks_output = gr.Markdown(label="Điều luật liên quan được retrieve")

    submit_btn.click(
        fn=answer_question,
        inputs=[question_input],
        outputs=[answer_output, sources_output, chunks_output],
    )

    gr.Examples(
        examples=[
            ["Hợp đồng vô hiệu khi nào?"],
            ["Tuổi kết hôn tối thiểu theo luật Việt Nam là bao nhiêu?"],
            ["Trách nhiệm bồi thường thiệt hại ngoài hợp đồng được quy định thế nào?"],
            ["Tội phạm được phân loại như thế nào?"],
        ],
        inputs=[question_input],
    )

if __name__ == "__main__":
    demo.launch(share=True)

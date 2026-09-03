"""Sinh cac hinh so lieu that cho giao trinh (offline, khong goi API).

Chay:  HF_HUB_OFFLINE=1 python3 make_figures.py
Xuat:  lectures/figures/*.pdf  +  *.png
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REPO)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})

BLUE = "#1a339a"
GREEN = "#008019"
GRAY = "#9aa0b4"
ORANGE = "#e07a1f"

FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ok", name)


def _barlabels(ax, bars, fmt="{:.0f}"):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                fmt.format(b.get_height()), ha="center", va="bottom", fontsize=10)


# ----------------------------------------------------------------------------
def fig_rag_split():
    labels = ["2026", "2023", "2021"]
    vals = [306, 208, 110]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    bars = ax.bar(labels, vals, color=BLUE, width=0.55)
    _barlabels(ax, bars)
    ax.set_ylabel("Số văn bản")
    ax.set_xlabel("Split (năm)")
    ax.set_title("Phân bố 624 văn bản UTS_VLC theo split")
    ax.set_ylim(0, max(vals) * 1.18)
    save(fig, "fig_rag_split")


def fig_model_comparison():
    path = os.path.join(REPO, "evaluation", "model_comparison.json")
    with open(path) as f:
        d = json.load(f)
    e5 = d["multilingual_e5_base"]
    sb = d["vietnamese_sbert"]
    groups = ["Hit Rate", "Avg Retrieval Score"]
    e5v = [e5["hit_rate"], e5["avg_retrieval_score"]]
    sbv = [sb["hit_rate"], sb["avg_retrieval_score"]]
    x = np.arange(len(groups))
    w = 0.35
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    b1 = ax.bar(x - w / 2, e5v, w, label="multilingual-e5-base", color=BLUE)
    b2 = ax.bar(x + w / 2, sbv, w, label="vietnamese-sbert", color=GRAY)
    _barlabels(ax, b1, "{:.4f}")
    _barlabels(ax, b2, "{:.4f}")
    ax.set_xticks(x, groups)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Giá trị (thang 0–1)")
    ax.set_title("So sánh hai mô hình embedding")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig_model_comparison")


# ----------------------------------------------------------------------------
def build_store():
    try:
        from src.embeddings.embedder import Embedder
        from src.vectorstore.store import VectorStore
        pd = os.path.join(REPO, "data", "chroma_db")
        store = VectorStore(embedder=Embedder(), persist_dir=pd)
        _ = store.query("kiem tra", top_k=1)
        return store
    except Exception as e:  # noqa: BLE001
        print("  WARN build_store that bai:", repr(e))
        return None


def _eval_scores(store):
    from evaluation.eval_dataset import EVAL_QUESTIONS
    per_q = []
    for item in EVAL_QUESTIONS:
        rows = store.query(item["question"], top_k=5)
        per_q.append([r["score"] for r in rows])
    return EVAL_QUESTIONS, per_q


def fig_eval_per_question(store):
    if store is None:
        print("  SKIP fig_eval_per_question (no store)")
        return
    qs, per_q = _eval_scores(store)
    means = [float(np.mean(s)) for s in per_q]
    overall = float(np.mean(means))
    labels = ["Q%d" % (i + 1) for i in range(len(qs))]
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    bars = ax.bar(labels, means, color=BLUE, width=0.6)
    _barlabels(ax, bars, "{:.3f}")
    ax.axhline(overall, color=ORANGE, ls="--", lw=1.3)
    ax.text(len(qs) - 0.5, 1.09, "Trung bình = %.4f" % overall,
            color=ORANGE, fontsize=9.5, ha="right", va="top")
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("Cosine score trung bình (top-5)")
    ax.set_title("Retrieval score trung bình theo từng câu hỏi")
    save(fig, "fig_eval_per_question")


def fig_score_hist(store):
    if store is None:
        print("  SKIP fig_score_hist (no store)")
        return
    _, per_q = _eval_scores(store)
    flat = np.array([s for row in per_q for s in row])
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.hist(flat, bins=12, range=(0.6, 1.0), color=BLUE, edgecolor="white")
    ax.axvline(float(flat.mean()), color=ORANGE, ls="--", lw=1.3,
               label="Trung bình = %.3f" % flat.mean())
    ax.set_xlabel("Cosine score")
    ax.set_ylabel("Số chunk (trong 50 chunk top-5)")
    ax.set_title("Phân bố điểm top-5 trên 10 câu đánh giá")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig_score_hist")


def fig_query_top5(store):
    if store is None:
        print("  SKIP fig_query_top5 (no store)")
        return
    from evaluation.eval_dataset import EVAL_QUESTIONS
    q = EVAL_QUESTIONS[0]["question"]  # "Hợp đồng vô hiệu khi nào?"
    rows = store.query(q, top_k=5)
    scores = [r["score"] for r in rows]
    labels = [(r["title"] or "?")[:26] for r in rows]
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    bars = ax.bar(range(len(scores)), scores, color=BLUE, width=0.6)
    _barlabels(ax, bars, "{:.3f}")
    ax.set_xticks(range(len(scores)), labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Cosine score")
    ax.set_title('Điểm 5 chunk top-k cho câu hỏi:\n"%s"' % q)
    save(fig, "fig_query_top5")


# ----------------------------------------------------------------------------
def fig_chunk_lenhist():
    lens = None
    note = ""
    try:
        from src.ingestion.loader import load_legal_documents
        from src.ingestion.chunker import chunk_documents
        docs = load_legal_documents(max_docs=15)
        chunks = chunk_documents(docs)
        lens = np.array([len(c["text"]) for c in chunks])
        note = "mẫu %d văn bản thật, %d chunk" % (len(docs), len(chunks))
    except Exception as e:  # noqa: BLE001
        print("  WARN chunk_lenhist fallback synthetic:", repr(e))
        rng = np.random.default_rng(0)
        lens = rng.lognormal(6.0, 0.5, 4000).clip(60, 3000)
        note = "dữ liệu tổng hợp (fallback)"
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.hist(lens, bins=40, range=(0, 2000), color=BLUE, edgecolor="white")
    ax.axvline(512, color=ORANGE, ls="--", lw=1.3, label="MAX_CHUNK_SIZE = 512")
    ax.set_xlabel("Độ dài chunk (ký tự)")
    ax.set_ylabel("Số chunk")
    ax.set_title("Phân bố độ dài chunk (%s)" % note)
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig_chunk_lenhist")


def fig_architecture():
    """So do kien truc he thong. Ve bang code de sinh lai duoc khi kien truc doi.

    Ban PNG cu trong latex_report/ ve khoi "Gradio UI" - da khong con dung ke tu
    khi thay Gradio bang FastAPI + giao dien web tu viet.
    """
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 5.4); ax.axis("off")

    def box(x, y, w, h, title, sub, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                                    linewidth=1.6, edgecolor=color, facecolor="white"))
        ax.text(x + w / 2, y + h - 0.30, title, ha="center", va="center",
                fontsize=10.5, fontweight="bold", color=color)
        for i, line in enumerate(sub):
            ax.text(x + w / 2, y + h - 0.62 - i * 0.27, line, ha="center", va="center",
                    fontsize=8.4, color="#444")

    def arrow(x1, y1, x2, y2, label=""):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=13, linewidth=1.2, color=GRAY))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.14, label, ha="center",
                    fontsize=8, color=GRAY)

    box(0.1, 3.5, 2.3, 1.5, "Trinh duyet", ["web/index.html", "app.js  field.js", "style.css"], BLUE)
    box(3.0, 3.5, 2.6, 1.5, "server.py (FastAPI)",
        ["POST /api/ask", "GET /api/ask/stream", "(SSE tung buoc)"], BLUE)
    box(6.3, 3.5, 3.5, 1.5, "RAGPipeline",
        ["store.query(top_k=10)", "generator.generate()"], BLUE)

    box(0.1, 1.5, 2.6, 1.5, "Ingestion",
        ["loader.py", "chunker.py", "tach theo Dieu"], GREEN)
    box(3.3, 1.5, 2.9, 1.5, "VectorStore (Chroma)",
        ["multilingual-e5-base", "48.803 chunk, cosine", "khu trung + tra so Dieu"], GREEN)
    box(6.8, 1.5, 3.0, 1.5, "Generator",
        ["API tuong thich OpenAI", "Gemini / Groq / ...", "trich dan [n]"], ORANGE)

    box(3.3, 0.05, 2.9, 1.0, "export_vector_map.py",
        ["PCA 768 -> 3 chieu", "web/vector_map.bin"], GRAY)

    arrow(2.4, 4.25, 3.0, 4.25, "HTTP")
    arrow(5.6, 4.25, 6.3, 4.25)
    arrow(7.4, 3.5, 5.6, 3.0)
    arrow(8.6, 3.5, 8.3, 3.0)
    arrow(2.7, 2.25, 3.3, 2.25, "index")
    arrow(4.7, 1.5, 4.7, 1.05)

    ax.text(5.0, 5.25, "Kien truc he thong RAG phap luat Viet Nam",
            ha="center", fontsize=12, fontweight="bold")
    save(fig, "fig_architecture")



def main():
    print("Sinh hinh ->", FIG)
    fig_architecture()
    fig_rag_split()
    fig_model_comparison()
    fig_chunk_lenhist()
    store = build_store()
    fig_eval_per_question(store)
    fig_score_hist(store)
    fig_query_top5(store)
    print("DONE ->", FIG)


if __name__ == "__main__":
    main()

import os
import sys
import time
import html

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

# ==============================================================================
# DESIGN SYSTEM — Institutional / editorial (Vietnamese legal reference)
# Light is the default palette; dark overrides live under `body.dark`
# (Gradio toggles that class on <body>). No emoji, no gradients, no glow.
# ==============================================================================
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Spectral:wght@400;500;600;700&display=swap');

:root {
    --paper: #FBF9F4;
    --card: #FFFFFF;
    --ink: #1A1A1A;
    --ink-2: #5C5C5C;
    --ink-3: #8A8A8A;
    --accent: #8B1A1A;
    --accent-soft: rgba(139, 26, 26, 0.08);
    --rule: #E0DACE;
    --rule-strong: #C9C0AC;
    --shadow: 0 1px 2px rgba(26, 26, 26, 0.04);
    --serif: 'Spectral', Georgia, 'Times New Roman', serif;
    --sans: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --mono: 'IBM Plex Mono', ui-monospace, 'SFMono-Regular', monospace;
}

body.dark {
    --paper: #1C1A17;
    --card: #242019;
    --ink: #EDE8DC;
    --ink-2: #B0A990;
    --ink-3: #807A68;
    --accent: #CE5A4E;
    --accent-soft: rgba(206, 90, 78, 0.12);
    --rule: #38342B;
    --rule-strong: #4A4436;
    --shadow: none;
}

/* ================= Base ================= */
body,
.gradio-container {
    font-family: var(--sans) !important;
    background: var(--paper) !important;
    color: var(--ink) !important;
}

.gradio-container {
    max-width: 1180px !important;
    margin: 0 auto !important;
}

.gradio-container a { color: var(--accent); }

.gradio-container footer { display: none !important; }

/* ================= Top utility bar (theme toggle) ================= */
#topbar {
    justify-content: flex-end !important;
    border: none !important;
    background: transparent !important;
    gap: 0 !important;
    margin-bottom: 2px;
    min-height: 0 !important;
}

#theme-toggle {
    flex: 0 0 auto !important;
    min-width: 0 !important;
}

#theme-toggle button,
button#theme-toggle {
    font-family: var(--mono) !important;
    font-size: 10.5px !important;
    font-weight: 500 !important;
    letter-spacing: 1px;
    text-transform: uppercase;
    background: transparent !important;
    color: var(--ink-3) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 3px !important;
    padding: 5px 11px !important;
    min-height: 0 !important;
    box-shadow: none !important;
}

#theme-toggle button:hover {
    color: var(--ink) !important;
    border-color: var(--rule-strong) !important;
}

/* ================= Masthead ================= */
.masthead {
    border-bottom: 2px solid var(--ink);
    padding: 2px 0 18px;
    margin-bottom: 10px;
}

.masthead-kicker {
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: 12px;
}

.masthead-title {
    font-family: var(--serif);
    font-size: 33px;
    font-weight: 600;
    line-height: 1.18;
    letter-spacing: -0.01em;
    color: var(--ink);
    margin: 0 0 10px;
}

.masthead-standfirst {
    font-size: 14.5px;
    line-height: 1.62;
    color: var(--ink-2);
    max-width: 68ch;
    margin: 0 0 14px;
}

.masthead-meta {
    font-family: var(--mono);
    font-size: 11.5px;
    line-height: 1.7;
    color: var(--ink-3);
}

/* ================= Tabs ================= */
.tab-nav {
    border-bottom: 1px solid var(--rule) !important;
    gap: 2px !important;
}

.tab-nav button {
    font-family: var(--sans) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em;
    color: var(--ink-3) !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 10px 14px !important;
}

.tab-nav button.selected,
.tab-nav button[aria-selected="true"] {
    color: var(--ink) !important;
    border-bottom-color: var(--accent) !important;
}

/* ================= Inputs ================= */
.gradio-container label span,
.gradio-container .block-title,
.gradio-container span[data-testid="block-info"] {
    font-family: var(--mono) !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--ink-3) !important;
}

.gradio-container textarea,
.gradio-container input[type="text"] {
    font-family: var(--sans) !important;
    font-size: 14px !important;
    background: var(--card) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule-strong) !important;
    border-radius: 3px !important;
    box-shadow: none !important;
}

.gradio-container textarea:focus,
.gradio-container input[type="text"]:focus {
    border-color: var(--accent) !important;
    outline: none !important;
    box-shadow: none !important;
}

/* ================= Buttons ================= */
.btn-legal-primary,
.btn-legal-primary button,
button.btn-legal-primary {
    background: var(--accent) !important;
    color: #ffffff !important;
    font-family: var(--sans) !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    letter-spacing: 0.01em;
    border: 1px solid var(--accent) !important;
    border-radius: 3px !important;
    box-shadow: none !important;
    transition: opacity 0.15s ease !important;
}

.btn-legal-primary button:hover,
button.btn-legal-primary:hover {
    opacity: 0.88 !important;
    transform: none !important;
    box-shadow: none !important;
}

.btn-legal-secondary,
.btn-legal-secondary button,
button.btn-legal-secondary {
    background: transparent !important;
    color: var(--ink-2) !important;
    font-family: var(--sans) !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    border: 1px solid var(--rule-strong) !important;
    border-radius: 3px !important;
    box-shadow: none !important;
}

.btn-legal-secondary button:hover,
button.btn-legal-secondary:hover {
    color: var(--ink) !important;
    border-color: var(--ink-3) !important;
    transform: none !important;
}

/* ================= Example-questions label ================= */
.block:has(> .gallery) > .label {
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--ink-3);
}

.block:has(> .gallery) > .label svg { display: none; }

/* ================= Example questions ================= */
.gradio-container .dataset button,
.gradio-container table.gr-samples-table td,
.gradio-container .gr-sample-textbox {
    font-family: var(--sans) !important;
    font-size: 12.5px !important;
    background: transparent !important;
    color: var(--ink-2) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 3px !important;
    box-shadow: none !important;
}

.gradio-container .dataset button:hover {
    border-color: var(--accent) !important;
    color: var(--ink) !important;
}

/* ================= Status line ================= */
.meta-status-bar {
    display: block;
    background: none;
    border: none;
    border-top: 1px solid var(--rule);
    border-radius: 0;
    padding: 10px 0 0;
    margin: 6px 0 14px;
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--ink-3);
}

.status-chip,
.status-chip-success {
    display: inline;
    color: var(--ink-3);
    background: none;
    border: none;
    padding: 0;
    font-weight: 400;
}

/* ================= Answer card ================= */
.legal-answer-card {
    background: var(--card);
    border: 1px solid var(--rule);
    border-left: 3px solid var(--accent);
    border-radius: 3px;
    padding: 22px 26px;
    box-shadow: var(--shadow);
    margin-bottom: 18px;
}

.answer-header-badge {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    border-bottom: 1px solid var(--rule);
    padding-bottom: 10px;
    margin-bottom: 14px;
}

.badge-title {
    font-family: var(--mono);
    font-weight: 500;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--accent);
}

.badge-sub {
    font-family: var(--mono);
    font-size: 10.5px;
    letter-spacing: 0.5px;
    color: var(--ink-3);
}

.answer-content-body {
    font-size: 15px;
    line-height: 1.72;
    color: var(--ink);
}

.answer-content-body strong { font-weight: 600; }

/* ================= Sources ================= */
.sources-card {
    background: none;
    border: none;
    border-top: 1px solid var(--rule);
    border-radius: 0;
    padding: 12px 0 0;
    margin-bottom: 16px;
}

.sources-card-title {
    font-family: var(--mono);
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: 6px;
}

.sources-wrapper {
    display: block;
    font-size: 13px;
    line-height: 1.6;
    color: var(--ink-2);
}

.source-tag {
    display: inline;
    background: none;
    border: none;
    padding: 0;
    color: var(--ink-2);
    font-weight: 500;
}

.source-tag::after {
    content: ";  ";
    color: var(--ink-3);
}

.source-tag:last-child::after { content: ""; }

/* ================= Retrieved chunks ================= */
.chunks-section-header {
    display: block;
    background: none;
    border: none;
    border-bottom: 2px solid var(--ink);
    border-radius: 0;
    margin-bottom: 12px;
    padding: 0 0 8px;
}

.chunks-section-title {
    display: block;
    font-family: var(--mono);
    font-weight: 500;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--ink);
}

.chunks-scroll-area {
    max-height: 720px;
    overflow-y: auto;
    padding-right: 4px;
}

.chunks-scroll-area::-webkit-scrollbar { width: 5px; }
.chunks-scroll-area::-webkit-scrollbar-track { background: transparent; }
.chunks-scroll-area::-webkit-scrollbar-thumb { background: var(--rule-strong); border-radius: 0; }

.law-chunk-card {
    background: var(--card);
    border: 1px solid var(--rule);
    border-radius: 3px;
    padding: 15px 17px;
    margin-bottom: 10px;
    box-shadow: none;
    transition: border-color 0.15s ease;
}

.law-chunk-card:hover {
    border-color: var(--rule-strong);
    transform: none;
    box-shadow: none;
}

.chunk-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--rule);
}

.chunk-title-area {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
}

.chunk-index {
    font-family: var(--mono);
    background: none;
    color: var(--ink-3);
    font-weight: 500;
    font-size: 12px;
    padding: 0;
    border-radius: 0;
}

.chunk-law-type {
    background: none;
    border: none;
    padding: 0;
    border-radius: 0;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--ink-3);
}

.chunk-doc-title {
    font-weight: 600;
    font-size: 13.5px;
    color: var(--ink);
}

.score-badge,
.score-high,
.score-med,
.score-low {
    font-family: var(--mono);
    font-size: 11.5px;
    font-weight: 500;
    padding: 0;
    border: none;
    border-radius: 0;
    background: none;
    color: var(--ink-2);
    white-space: nowrap;
}

.chunk-text {
    font-size: 12.5px;
    line-height: 1.7;
    color: var(--ink-2);
    background: transparent;
    border-left: 2px solid var(--rule-strong);
    border-radius: 0;
    padding: 2px 0 2px 14px;
    white-space: pre-wrap;
    font-family: var(--sans);
}

/* ================= Empty state ================= */
.empty-state-card {
    text-align: left;
    background: none;
    border: none;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    border-radius: 0;
    padding: 22px 0;
    margin-bottom: 18px;
}

.empty-title {
    font-family: var(--serif);
    font-size: 16px;
    font-weight: 600;
    color: var(--ink-2);
    margin-bottom: 6px;
}

.empty-desc {
    font-size: 13px;
    color: var(--ink-3);
    max-width: 62ch;
    margin: 0;
    line-height: 1.6;
}

/* ================= Document sections (architecture / guide) ================= */
.doc-section { padding: 6px 0 4px; }

.doc-h2 {
    font-family: var(--serif);
    font-size: 22px;
    font-weight: 600;
    color: var(--ink);
    margin: 0 0 6px;
}

.doc-h3 {
    font-family: var(--serif);
    font-size: 18px;
    font-weight: 600;
    color: var(--ink);
    margin: 28px 0 8px;
}

.doc-lede {
    color: var(--ink-2);
    font-size: 14px;
    line-height: 1.62;
    margin: 0 0 20px;
    max-width: 72ch;
}

.arch-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(258px, 1fr));
    gap: 1px;
    margin: 14px 0 8px;
    background: var(--rule);
    border: 1px solid var(--rule);
}

.arch-card {
    background: var(--card);
    border: none;
    border-radius: 0;
    padding: 18px 20px;
    box-shadow: none;
}

.arch-card-step {
    font-family: var(--mono);
    font-size: 10.5px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: 7px;
}

.arch-card-title {
    font-family: var(--serif);
    font-weight: 600;
    font-size: 15px;
    color: var(--ink);
    margin-bottom: 6px;
}

.arch-card-desc {
    font-size: 12.5px;
    color: var(--ink-2);
    line-height: 1.6;
}

.arch-card-desc code,
.doc-note code {
    font-family: var(--mono);
    font-size: 11.5px;
    background: var(--accent-soft);
    padding: 1px 4px;
    border-radius: 2px;
    color: var(--ink);
}

/* ================= Benchmark table ================= */
.benchmark-table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 8px;
    background: none;
    border: none;
    border-top: 2px solid var(--ink);
    border-bottom: 2px solid var(--ink);
    border-radius: 0;
    overflow: hidden;
}

.benchmark-table th {
    background: none;
    color: var(--ink);
    text-align: left;
    padding: 10px 16px 10px 0;
    font-family: var(--mono);
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--ink);
}

.benchmark-table td {
    padding: 11px 16px 11px 0;
    border-bottom: 1px solid var(--rule);
    font-size: 13px;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
}

.benchmark-table td:first-child { color: var(--ink); }
.benchmark-table tr:last-child td { border-bottom: none; }

.benchmark-highlight {
    font-weight: 600;
    color: var(--ink) !important;
    background: none !important;
}

/* ================= Notes / disclaimer ================= */
.doc-note {
    background: var(--card);
    border: 1px solid var(--rule);
    border-radius: 3px;
    padding: 20px 22px;
    margin-bottom: 16px;
}

.doc-note.is-warning { border-left: 3px solid var(--accent); }

.doc-note h4 {
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--ink-3);
    margin: 0 0 10px;
}

.doc-note ul {
    margin: 0;
    padding-left: 18px;
    color: var(--ink-2);
    font-size: 13.5px;
    line-height: 1.75;
}

.doc-note p {
    margin: 0;
    color: var(--ink-2);
    font-size: 13px;
    line-height: 1.7;
}

.doc-meta {
    border-top: 1px solid var(--rule);
    padding-top: 14px;
    font-size: 12.5px;
    color: var(--ink-3);
    line-height: 1.9;
}

.doc-meta strong { color: var(--ink-2); font-weight: 600; }

/* ================= Footer ================= */
.doc-footer {
    margin-top: 26px;
    padding: 16px 0 22px;
    border-top: 2px solid var(--ink);
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.5px;
    color: var(--ink-3);
}
"""

# ==============================================================================
# GRADIO THEME — keeps Gradio's own chrome aligned with the CSS, both modes
# ==============================================================================
LEGAL_THEME = gr.themes.Base(
    font=("IBM Plex Sans", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"),
    font_mono=("IBM Plex Mono", "ui-monospace", "monospace"),
    radius_size="sm",
).set(
    body_background_fill="#FBF9F4",
    body_background_fill_dark="#1C1A17",
    body_text_color="#1A1A1A",
    body_text_color_dark="#EDE8DC",
    body_text_color_subdued="#8A8A8A",
    body_text_color_subdued_dark="#807A68",
    background_fill_primary="#FFFFFF",
    background_fill_primary_dark="#242019",
    background_fill_secondary="#FBF9F4",
    background_fill_secondary_dark="#1C1A17",
    border_color_primary="#E0DACE",
    border_color_primary_dark="#38342B",
    block_background_fill="#FFFFFF",
    block_background_fill_dark="#242019",
    block_border_color="#E0DACE",
    block_border_color_dark="#38342B",
    block_label_text_color="#8A8A8A",
    block_label_text_color_dark="#807A68",
    block_title_text_color="#5C5C5C",
    block_title_text_color_dark="#B0A990",
    input_background_fill="#FFFFFF",
    input_background_fill_dark="#242019",
    input_border_color="#C9C0AC",
    input_border_color_dark="#4A4436",
    color_accent="#8B1A1A",
    color_accent_soft="rgba(139, 26, 26, 0.08)",
    button_primary_background_fill="#8B1A1A",
    button_primary_background_fill_dark="#CE5A4E",
    button_primary_background_fill_hover="#7A1717",
    button_primary_text_color="#FFFFFF",
    button_primary_border_color="#8B1A1A",
    button_secondary_background_fill="transparent",
    button_secondary_background_fill_dark="transparent",
    button_secondary_border_color="#C9C0AC",
    button_secondary_text_color="#5C5C5C",
)

# Applied once on page load — restores the viewer's saved light/dark choice.
THEME_INIT_JS = """
() => {
  try {
    const saved = localStorage.getItem('legalTheme');
    if (saved === 'dark') document.body.classList.add('dark');
    else if (saved === 'light') document.body.classList.remove('dark');
  } catch (e) {}
}
"""

# Toggles the mode and remembers it for next time.
THEME_TOGGLE_JS = """
() => {
  const isDark = document.body.classList.toggle('dark');
  try { localStorage.setItem('legalTheme', isDark ? 'dark' : 'light'); } catch (e) {}
}
"""

# ==============================================================================
# STATIC CONTENT BLOCKS
# ==============================================================================
MASTHEAD_HTML = """
<div class="masthead">
    <div class="masthead-kicker">Hệ thống tra cứu pháp luật Việt Nam &middot; Retrieval-Augmented Generation</div>
    <h1 class="masthead-title">Hỏi đáp căn cứ pháp lý theo Điều, Khoản luật</h1>
    <p class="masthead-standfirst">
        Truy xuất các điều luật liên quan từ kho văn bản quy phạm pháp luật đã số hóa và tổng hợp
        câu trả lời có dẫn nguồn. Kết quả chỉ mang tính tham khảo học thuật.
    </p>
    <div class="masthead-meta">
        48.803 điều luật &middot; 624 văn bản quy phạm pháp luật &middot; truy xuất Top-5 &middot;
        embedding multilingual-e5-base &middot; ChromaDB (HNSW, cosine) &middot; sinh câu trả lời bằng Gemini
    </div>
</div>
"""

INITIAL_ANSWER_PLACEHOLDER = """
<div class="empty-state-card">
    <div class="empty-title">Chưa có câu hỏi</div>
    <div class="empty-desc">
        Nhập câu hỏi pháp lý ở ô bên trên hoặc chọn một câu hỏi mẫu. Hệ thống sẽ trích xuất các
        điều luật liên quan và tổng hợp câu trả lời kèm nguồn dẫn.
    </div>
</div>
"""

INITIAL_CHUNKS_PLACEHOLDER = """
<div class="empty-state-card">
    <div class="empty-title">Chưa có dữ liệu trích xuất</div>
    <div class="empty-desc">
        Các điều luật liên quan, tìm bằng tìm kiếm ngữ nghĩa, sẽ hiển thị ở đây kèm điểm tương đồng cosine.
    </div>
</div>
"""

ARCHITECTURE_HTML = """
<div class="doc-section">
    <h2 class="doc-h2">Kiến trúc hệ thống RAG</h2>
    <p class="doc-lede">
        Quy trình bốn giai đoạn: phân đoạn văn bản theo cấu trúc điều luật, biểu diễn vector,
        lập chỉ mục và truy xuất, tổng hợp câu trả lời chỉ dựa trên ngữ cảnh được cung cấp.
    </p>

    <div class="arch-grid">
        <div class="arch-card">
            <div class="arch-card-step">Giai đoạn 01</div>
            <div class="arch-card-title">Phân đoạn văn bản</div>
            <div class="arch-card-desc">
                Tách theo cấu trúc Điều/Khoản bằng biểu thức chính quy <code>(?=Điều\\s+\\d+\\.)</code>,
                giữ trọn ngữ cảnh mỗi điều. Thu được 48.803 đoạn từ 624 văn bản quy phạm pháp luật.
            </div>
        </div>
        <div class="arch-card">
            <div class="arch-card-step">Giai đoạn 02</div>
            <div class="arch-card-title">Mô hình embedding</div>
            <div class="arch-card-desc">
                <code>intfloat/multilingual-e5-base</code> (278M tham số, 768 chiều). Tiền tố
                <code>passage:</code> và <code>query:</code> theo đúng quy ước huấn luyện của mô hình.
            </div>
        </div>
        <div class="arch-card">
            <div class="arch-card-step">Giai đoạn 03</div>
            <div class="arch-card-title">Cơ sở dữ liệu vector</div>
            <div class="arch-card-desc">
                ChromaDB, chỉ mục HNSW với khoảng cách cosine. Nạp theo lô 500 đoạn mỗi lần,
                truy xuất năm điều luật tương đồng nhất cho mỗi câu hỏi.
            </div>
        </div>
        <div class="arch-card">
            <div class="arch-card-step">Giai đoạn 04</div>
            <div class="arch-card-title">Sinh câu trả lời</div>
            <div class="arch-card-desc">
                Google Gemini với prompt ràng buộc: chỉ trả lời dựa trên ngữ cảnh truy xuất,
                nêu rõ nguồn luật, không suy diễn ngoài dữ liệu.
            </div>
        </div>
    </div>

    <h3 class="doc-h3">Kết quả đánh giá thực nghiệm</h3>
    <table class="benchmark-table">
        <thead>
            <tr>
                <th>Chỉ số</th>
                <th>multilingual-e5-base</th>
                <th>vietnamese-sbert</th>
                <th>Chênh lệch</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Hit Rate (tỷ lệ tìm đúng)</td>
                <td class="benchmark-highlight">100% (1,0)</td>
                <td>100% (1,0)</td>
                <td>Ngang nhau trên 10 câu kiểm thử</td>
            </tr>
            <tr>
                <td>Điểm tương đồng trung bình</td>
                <td class="benchmark-highlight">0,8765</td>
                <td>0,6207</td>
                <td>Cao hơn 41,2%</td>
            </tr>
            <tr>
                <td>Kích thước mô hình / số chiều</td>
                <td>278M tham số / 768</td>
                <td>110M tham số / 768</td>
                <td>Mô hình đa ngữ quy mô lớn hơn</td>
            </tr>
            <tr>
                <td>Quy mô tập thực nghiệm</td>
                <td>Toàn bộ (48.803 đoạn)</td>
                <td>Tập con (100 văn bản)</td>
                <td>Đánh giá trên toàn kho luật</td>
            </tr>
        </tbody>
    </table>
</div>
"""

DISCLAIMER_HTML = """
<div class="doc-section">
    <h2 class="doc-h2">Hướng dẫn tra cứu và tuyên bố pháp lý</h2>

    <div class="doc-note">
        <h4>Cách đặt câu hỏi để có kết quả chính xác</h4>
        <ul>
            <li>Nêu rõ quan hệ pháp luật cần hỏi. Thay vì &ldquo;Tôi phải làm gì?&rdquo;, hãy hỏi
                &ldquo;Người lao động có quyền đơn phương chấm dứt hợp đồng lao động trong trường hợp nào?&rdquo;.</li>
            <li>Hỏi thẳng vào điều kiện, thời hiệu hoặc chế tài, ví dụ
                &ldquo;Thời hiệu khởi kiện tranh chấp hợp đồng dân sự là bao lâu?&rdquo;.</li>
            <li>Đối chiếu danh sách điều luật trích xuất ở cột bên phải với văn bản gốc.</li>
        </ul>
    </div>

    <div class="doc-note is-warning">
        <h4>Tuyên bố miễn trừ trách nhiệm</h4>
        <p>
            Đây là sản phẩm học thuật phục vụ nghiên cứu, học tập trong môn Xử lý Ngôn ngữ Tự nhiên.
            Nội dung giải đáp do mô hình ngôn ngữ lớn tổng hợp tự động từ dữ liệu văn bản quy phạm pháp luật
            được số hóa, không cấu thành ý kiến tư vấn pháp lý chính thức. Trong tình huống pháp lý cụ thể,
            người dùng cần tham chiếu văn bản gốc hoặc xin ý kiến chuyên gia.
        </p>
    </div>

    <div class="doc-meta">
        <strong>Đề tài:</strong> Báo cáo Bài tập lớn Xử lý Ngôn ngữ Tự nhiên (INT547032)<br/>
        <strong>Sinh viên thực hiện:</strong> Hồ Minh Hiếu &mdash; MSSV 31241022078 &mdash; Lớp 26C1INT54703201<br/>
        <strong>Giảng viên hướng dẫn:</strong> ThS. Nguyễn Khắc Toàn
    </div>
</div>
"""

FOOTER_HTML = """
<div class="doc-footer">
    Vietnam Legal RAG QA &middot; multilingual-e5-base &middot; ChromaDB &middot; Gemini &middot; Hồ Minh Hiếu
</div>
"""

CHUNKS_HEADER_HTML = """
<div class="chunks-section-header">
    <span class="chunks-section-title">Căn cứ pháp lý trích xuất &mdash; Top-5</span>
</div>
"""

# ==============================================================================
# PIPELINE INVOCATION & UI ADAPTER (Pure UI Formatting, Zero Logic Change)
# ==============================================================================
def answer_question(question: str):
    if not question or not question.strip():
        return INITIAL_ANSWER_PLACEHOLDER, "", INITIAL_CHUNKS_PLACEHOLDER, ""

    start_time = time.time()
    result = pipeline.ask(question)
    elapsed = time.time() - start_time

    answer = result.get("answer", "Không tìm thấy nội dung trả lời phù hợp.")
    sources = result.get("sources", [])
    chunks = result.get("retrieved_chunks", [])

    # Status line
    status_html = f"""
    <div class="meta-status-bar">
        <span class="status-chip">Xử lý {elapsed:.2f}s</span>
        <span class="status-chip"> &middot; {len(sources)} văn bản</span>
        <span class="status-chip"> &middot; {len(chunks)} điều luật</span>
        <span class="status-chip status-chip-success"> &middot; đã đối chiếu văn bản gốc</span>
    </div>
    """

    # Sources as a plain inline list
    if sources:
        sources_html = '<div class="sources-card">'
        sources_html += '<div class="sources-card-title">Căn cứ pháp lý</div>'
        sources_html += '<div class="sources-wrapper">'
        for s in sources:
            safe_s = html.escape(str(s))
            sources_html += f'<span class="source-tag">{safe_s}</span>'
        sources_html += '</div></div>'
    else:
        sources_html = ""

    # Answer card
    answer_md = f"""
<div class="legal-answer-card">
    <div class="answer-header-badge">
        <span class="badge-title">Nội dung giải đáp</span>
        <span class="badge-sub">Đối chiếu văn bản hiện hành</span>
    </div>
    <div class="answer-content-body">

{answer}

    </div>
</div>
"""

    # Retrieved chunks as individual cards
    chunks_md = '<div class="chunks-scroll-area">'
    for i, chunk in enumerate(chunks, 1):
        score = chunk.get("score", 0.0)
        title = html.escape(str(chunk.get("title", f"Điều luật #{i}")))
        law_type = html.escape(str(chunk.get("law_type", "Văn bản luật")))
        text = html.escape(str(chunk.get("text", "")).strip())

        if score >= 0.85:
            score_class = "score-high"
        elif score >= 0.75:
            score_class = "score-med"
        else:
            score_class = "score-low"
        score_label = f"{score:.4f}"

        chunks_md += f"""
<div class="law-chunk-card">
    <div class="chunk-header">
        <div class="chunk-title-area">
            <span class="chunk-index">{i:02d}</span>
            <span class="chunk-law-type">{law_type}</span>
            <span class="chunk-doc-title">{title}</span>
        </div>
        <span class="score-badge {score_class}">{score_label}</span>
    </div>
    <div class="chunk-text">{text}</div>
</div>
"""
    chunks_md += "</div>"

    return answer_md, sources_html, chunks_md, status_html

def clear_all():
    return "", INITIAL_ANSWER_PLACEHOLDER, "", INITIAL_CHUNKS_PLACEHOLDER, ""

# ==============================================================================
# GRADIO APPLICATION LAYOUT
# ==============================================================================
with gr.Blocks(title="VN Legal RAG QA System") as demo:
    with gr.Row(elem_id="topbar"):
        theme_toggle_btn = gr.Button("Sáng / Tối", elem_id="theme-toggle", scale=0)

    gr.HTML(MASTHEAD_HTML)

    with gr.Tabs():
        with gr.TabItem("Tra cứu & giải đáp", id="tab_qa"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=7):
                    question_input = gr.Textbox(
                        label="Câu hỏi pháp lý",
                        placeholder="Ví dụ: Hợp đồng vô hiệu trong những trường hợp nào?",
                        lines=3,
                        max_lines=6,
                    )

                    with gr.Row():
                        submit_btn = gr.Button(
                            "Tra cứu & giải đáp",
                            variant="primary",
                            elem_classes=["btn-legal-primary"],
                            scale=3,
                        )
                        clear_btn = gr.Button(
                            "Xóa",
                            variant="secondary",
                            elem_classes=["btn-legal-secondary"],
                            scale=1,
                        )

                    status_output = gr.HTML()
                    answer_output = gr.Markdown(value=INITIAL_ANSWER_PLACEHOLDER)
                    sources_output = gr.HTML()

                    gr.Examples(
                        label="Câu hỏi mẫu",
                        examples=[
                            ["Hợp đồng vô hiệu khi nào?"],
                            ["Tuổi kết hôn tối thiểu theo luật Việt Nam là bao nhiêu?"],
                            ["Trách nhiệm bồi thường thiệt hại ngoài hợp đồng được quy định thế nào?"],
                            ["Tội phạm được phân loại như thế nào theo Bộ luật Hình sự?"],
                            ["Điều kiện để di chúc có hiệu lực pháp luật là gì?"],
                            ["Thời hiệu khởi kiện vụ án dân sự là bao lâu?"],
                        ],
                        inputs=[question_input],
                    )

                with gr.Column(scale=5):
                    gr.HTML(CHUNKS_HEADER_HTML)
                    chunks_output = gr.HTML(value=INITIAL_CHUNKS_PLACEHOLDER)

        with gr.TabItem("Kiến trúc & đánh giá", id="tab_benchmark"):
            gr.HTML(ARCHITECTURE_HTML)

        with gr.TabItem("Hướng dẫn & tuyên bố pháp lý", id="tab_guide"):
            gr.HTML(DISCLAIMER_HTML)

    gr.HTML(FOOTER_HTML)

    # Event handlers
    submit_btn.click(
        fn=answer_question,
        inputs=[question_input],
        outputs=[answer_output, sources_output, chunks_output, status_output],
    )
    question_input.submit(
        fn=answer_question,
        inputs=[question_input],
        outputs=[answer_output, sources_output, chunks_output, status_output],
    )
    clear_btn.click(
        fn=clear_all,
        inputs=[],
        outputs=[question_input, answer_output, sources_output, chunks_output, status_output],
    )

    # Light/dark: restore saved choice on load, toggle + persist on click
    demo.load(fn=None, inputs=None, outputs=None, js=THEME_INIT_JS)
    theme_toggle_btn.click(fn=None, inputs=None, outputs=None, js=THEME_TOGGLE_JS)

if __name__ == "__main__":
    demo.launch(css=CUSTOM_CSS, theme=LEGAL_THEME)

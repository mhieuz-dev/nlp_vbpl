---
title: luật.ai
emoji: ⚖️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# luật.ai — hỏi đáp văn bản quy phạm pháp luật Việt Nam

Hệ thống RAG trả lời câu hỏi pháp luật và **dẫn về đúng điều khoản gốc**, thay vì
tóm tắt chung chung. Đồ án môn Xử lý ngôn ngữ tự nhiên, UEH.

## Cách hoạt động

Câu hỏi được nhúng bằng `multilingual-e5-base`, tra trong ChromaDB (cosine HNSW)
lấy top-10 điều luật, rồi mô hình sinh viết câu trả lời **chỉ dựa trên** những
điều luật đó. Nếu kho không chứa câu trả lời, hệ thống **từ chối trả lời** thay
vì ghép các điều gần chủ đề lại cho nghe xuôi tai.

Kho hiện có **49.063 điều** từ **624 văn bản**: luật, bộ luật, hiến pháp và nghị
định. Phần nghị định được crawl từ [Công báo điện tử](https://congbao.chinhphu.vn)
(`robots.txt` cho phép), cập nhật hàng ngày qua GitHub Actions.

## Chạy ở máy

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # rồi điền LLM_API_KEY
python -m uvicorn server:app --reload
```

Mở http://127.0.0.1:8000. Chạy test: `pytest -q`.

## Cập nhật kho

```bash
python scripts/refresh_corpus.py --recent --dry-run      # xem có gì mới
python scripts/refresh_corpus.py --recent                 # nạp vào kho
python scripts/refresh_corpus.py --sweep 43550 43960 --types decree
```

## Đo chất lượng

`evaluation/retrieval_eval.py` chấm trên 22 câu hỏi có đáp án đã kiểm chứng
(luật nào, điều số mấy). Kết quả hiện tại: **Recall@5 0,864 · MRR 0,712 ·
Recall@10 0,955**.

Ghi chép quá trình, các hướng đã thử và đã loại nằm trong `memory.md`.

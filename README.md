# H2N LAW - hỏi đáp văn bản quy phạm pháp luật Việt Nam

Hệ thống RAG trả lời câu hỏi pháp luật và **dẫn về đúng điều khoản gốc**, thay vì
tóm tắt chung chung. Đồ án môn Xử lý ngôn ngữ tự nhiên, UEH.

## Cách hoạt động

Câu hỏi được nối thêm thuật ngữ pháp lý khi viết bằng lời đời thường ("vượt đèn
đỏ" -> "không chấp hành hiệu lệnh của đèn tín hiệu giao thông"), nhúng bằng
`multilingual-e5-base`, tra trong ChromaDB (cosine HNSW) lấy top-15 đoạn luật và
cắt cho vừa trần 16.000 ký tự, rồi mô hình sinh viết câu trả lời **chỉ dựa trên**
những đoạn đó. Câu hỏi nêu đích danh "Điều N" được tra thẳng theo số điều. Nếu
kho không chứa câu trả lời, hệ thống **từ chối trả lời** thay vì ghép các điều
gần chủ đề lại cho nghe xuôi tai.

Kho trên bản deploy (25/09/2026) có **53.338 đoạn** (một Điều dài bị chia nhiều
đoạn) từ **699 văn bản**: luật, bộ luật, hiến pháp, nghị định, thông tư, nghị
quyết và quyết định. Văn bản mới được crawl từ [Công báo điện tử](https://congbao.chinhphu.vn)
(`robots.txt` cho phép) mỗi đêm qua GitHub Actions.

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

`python -m evaluation.retrieval_eval` chấm truy xuất trên 42 câu hỏi có đáp án đã
kiểm chứng trong kho (22 câu văn phong gần luật + 20 câu lời đời thường), đi qua
đúng đường truy xuất của app. Một câu tính là trúng khi lấy được đúng phiên bản
văn bản, đúng Điều, và với nghị định giao thông là đúng đoạn chứa khoản có đáp án.
Số dưới đây đo trên kho 53.338 đoạn / 699 văn bản, trùng với bản deploy ngày 25/09/2026.

| Từ điển thuật ngữ | Recall@5 | Recall@10 | MRR@15 | Nguồn đúng còn trong context |
|---|---|---|---|---|
| tắt | 0,738 | 0,857 | 0,573 | 0,905 |
| **bật (app đang dùng)** | **0,881** | **0,976** | **0,689** | **0,976** |

Riêng 20 câu lời đời thường, Recall@5 tăng từ 0,60 lên 0,90. Câu còn trượt: "Muốn
hợp đồng có giá trị pháp lý thì cần điều kiện gì?" (Điều 117 BLDS ngoài top-15).

Ghi chép quá trình, các hướng đã thử và đã loại nằm trong `memory.md`.

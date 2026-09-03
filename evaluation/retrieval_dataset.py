"""Ground truth cho eval truy xuất.

Mỗi `expected` là (khoá tên luật đã bỏ dấu, số điều). Toàn bộ đã được kiểm
chứng có thật trong `data/chroma_db` bằng cách quét 31.262 cặp (luật, điều)
duy nhất trong kho, không phải viết theo trí nhớ.

Bộ này CỐ Ý gồm ba loại khó, vì bộ eval cũ 10 câu quá dễ (hit_rate 1.0 cho cả
hai embedder nên không phân biệt được gì):
  - lệch từ vựng: người hỏi dùng "hợp đồng", luật viết "giao dịch dân sự"
  - nêu đích danh số điều: dense embedding rất kém với token chính xác
  - dễ lẫn sang luật khác cùng chủ đề (dân sự / tố tụng dân sự / thi hành án dân sự)
"""

RETRIEVAL_QUESTIONS = [
    # --- lệch từ vựng ---
    {"question": "Hợp đồng vô hiệu khi nào?",
     "expected": [("bo luat dan su", 407)]},
    {"question": "Giao dịch dân sự vô hiệu trong trường hợp nào?",
     "expected": [("bo luat dan su", 122)]},
    {"question": "Muốn hợp đồng có giá trị pháp lý thì cần điều kiện gì?",
     "expected": [("bo luat dan su", 117)]},

    # --- nêu đích danh số điều (điểm yếu của dense, điểm mạnh của BM25) ---
    {"question": "Điều 117 Bộ luật Dân sự quy định gì?",
     "expected": [("bo luat dan su", 117)]},
    {"question": "Điều 630 Bộ luật Dân sự nói về vấn đề gì?",
     "expected": [("bo luat dan su", 630)]},
    {"question": "Nội dung Điều 9 Bộ luật Hình sự là gì?",
     "expected": [("bo luat hinh su", 9)]},
    {"question": "Điều 105 Bộ luật Lao động quy định thế nào?",
     "expected": [("bo luat lao dong", 105)]},

    # --- câu hỏi thường ---
    {"question": "Tuổi kết hôn tối thiểu theo luật Việt Nam là bao nhiêu?",
     "expected": [("luat hon nhan va gia dinh", 8)]},
    {"question": "Ai có quyền yêu cầu ly hôn?",
     "expected": [("luat hon nhan va gia dinh", 51)]},
    {"question": "Di chúc thế nào thì được coi là hợp pháp?",
     "expected": [("bo luat dan su", 630)]},
    {"question": "Thời hiệu thừa kế là bao lâu?",
     "expected": [("bo luat dan su", 623)]},
    {"question": "Thời hiệu khởi kiện tranh chấp hợp đồng là mấy năm?",
     "expected": [("bo luat dan su", 429)]},
    {"question": "Khi nào phát sinh trách nhiệm bồi thường thiệt hại ngoài hợp đồng?",
     "expected": [("bo luat dan su", 584)]},
    {"question": "Quyền sở hữu gồm những quyền gì?",
     "expected": [("bo luat dan su", 158)]},
    {"question": "Lãi suất cho vay tối đa được pháp luật quy định ra sao?",
     "expected": [("bo luat dan su", 468)]},
    {"question": "Tội phạm được phân loại như thế nào?",
     "expected": [("bo luat hinh su", 9)]},
    {"question": "Bao nhiêu tuổi thì phải chịu trách nhiệm hình sự?",
     "expected": [("bo luat hinh su", 12)]},
    {"question": "Hình phạt tù có thời hạn tối đa bao nhiêu năm?",
     "expected": [("bo luat hinh su", 38)]},
    {"question": "Hợp đồng lao động bị vô hiệu trong trường hợp nào?",
     "expected": [("bo luat lao dong", 49)]},
    {"question": "Thời giờ làm việc bình thường của người lao động là bao nhiêu?",
     "expected": [("bo luat lao dong", 105)]},
    {"question": "Hợp đồng lao động chấm dứt trong những trường hợp nào?",
     "expected": [("bo luat lao dong", 34)]},

    # --- dễ lẫn sang luật khác cùng chủ đề ---
    {"question": "Thời hiệu khởi kiện vụ án dân sự tại toà án được tính thế nào?",
     "expected": [("bo luat to tung dan su", 184)]},
]

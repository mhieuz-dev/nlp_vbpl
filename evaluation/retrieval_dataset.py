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


# Khoá tên nghị định: `_norm` bỏ hết chữ số nên "168/2024" biến mất, không dùng
# số hiệu làm khoá được. Cụm chữ dưới đây đã kiểm là nằm trong tên văn bản.
_ND_GIAO_THONG = "xu phat vi pham hanh chinh ve trat tu"

# Bộ câu hỏi LỜI NÓI ĐỜI THƯỜNG.
#
# Vì sao cần bộ riêng: bộ 22 câu ở trên phần lớn đã dùng sẵn từ ngữ gần với văn
# phong luật, nên nó không đo được điểm yếu thật sự phát hiện ngày 19/09/2026 -
# người ta hỏi "vượt đèn đỏ" trong khi luật viết "không chấp hành hiệu lệnh của
# đèn tín hiệu giao thông", và chunk đúng rơi xuống hạng 13, ngoài top-10.
#
# Mọi cặp (luật, điều) dưới đây đều tra thẳng từ `data/chroma_db` bằng tiêu đề
# điều luật, không viết theo trí nhớ. Câu hỏi thì cố ý viết bằng lời người
# thường hỏi, KHÔNG mượn từ ngữ của điều luật - nếu mượn thì bộ đánh giá tự làm
# bài dễ đi và con số đo được sẽ nói dối.
COLLOQUIAL_QUESTIONS = [
    # --- giao thông: khoảng cách từ vựng lớn nhất ---
    {"question": "Ô tô vượt đèn đỏ bị phạt bao nhiêu tiền?",
     "expected": [(_ND_GIAO_THONG, 6)]},
    {"question": "Xe máy vượt đèn đỏ phạt bao nhiêu?",
     "expected": [(_ND_GIAO_THONG, 7)]},
    {"question": "Đi xe máy không đội mũ bảo hiểm bị phạt nhiêu tiền?",
     "expected": [(_ND_GIAO_THONG, 7)]},
    {"question": "Uống rượu bia lái ô tô bị phạt thế nào?",
     "expected": [(_ND_GIAO_THONG, 6)]},
    {"question": "Nhậu xong chạy xe máy bị phạt bao nhiêu?",
     "expected": [(_ND_GIAO_THONG, 7)]},
    {"question": "Ô tô chạy quá tốc độ trên 35 km/h phạt bao nhiêu?",
     "expected": [(_ND_GIAO_THONG, 6)]},

    # --- lao động ---
    {"question": "Một năm được nghỉ phép mấy ngày?",
     "expected": [("bo luat lao dong", 113)]},
    {"question": "Tăng ca thì được trả thêm bao nhiêu phần trăm lương?",
     "expected": [("bo luat lao dong", 98)]},
    {"question": "Công ty đuổi việc nhân viên trong trường hợp nào?",
     "expected": [("bo luat lao dong", 125)]},
    {"question": "Thử việc được bao lâu thì phải ký hợp đồng chính thức?",
     "expected": [("bo luat lao dong", 25)]},
    {"question": "Lương thử việc thấp nhất là bao nhiêu?",
     "expected": [("bo luat lao dong", 26)]},

    # --- hôn nhân gia đình ---
    {"question": "Ly hôn thì chia tài sản ra sao?",
     "expected": [("luat hon nhan va gia dinh", 59)]},
    {"question": "Bỏ nhau rồi ai được quyền nuôi con?",
     "expected": [("luat hon nhan va gia dinh", 81)]},

    # --- hình sự: tên tội danh đời thường khác hẳn tên tội danh trong luật ---
    {"question": "Ăn trộm đồ thì bị tội gì?",
     "expected": [("bo luat hinh su", 173)]},
    {"question": "Đánh người gây thương tích bị xử lý thế nào?",
     "expected": [("bo luat hinh su", 134)]},
    {"question": "Lừa tiền người khác bị phạt tù bao nhiêu năm?",
     "expected": [("bo luat hinh su", 174)]},
    {"question": "Trốn thuế bao nhiêu thì bị đi tù?",
     "expected": [("bo luat hinh su", 200)]},

    # --- dân sự ---
    {"question": "Cho vay lãi bao nhiêu thì bị coi là cho vay nặng lãi?",
     "expected": [("bo luat dan su", 468)]},
    {"question": "Đặt cọc mua nhà rồi đổi ý thì có mất cọc không?",
     "expected": [("bo luat dan su", 328)]},
    {"question": "Làm hư đồ của người khác thì phải đền không?",
     "expected": [("bo luat dan su", 584)]},
]

# Dùng khi muốn một con số chung cho cả hai loại câu hỏi.
ALL_QUESTIONS = RETRIEVAL_QUESTIONS + COLLOQUIAL_QUESTIONS

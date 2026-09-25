"""Ground truth cho eval truy xuất.

Mỗi `expected` là (tập doc_id hợp lệ, số điều) hoặc (tập doc_id, số điều,
đoạn bằng chứng). Toàn bộ đã được kiểm chứng có thật trong `data/chroma_db`,
không phải viết theo trí nhớ.

Vì sao so theo doc_id chứ không theo tên văn bản: trước đây khoá là tên luật đã
bỏ dấu VÀ bỏ chữ số, nên khoá Bộ luật Hình sự khớp luôn cả hai luật sửa đổi
12/2017/QH14 và 86/2025/QH15 - phiên bản nào cũng được tính là trúng. Mỗi bộ
luật lại có mặt 3 lần trong kho dưới 3 doc_id (cùng số chunk, cùng nội dung),
nên tập hợp lệ liệt kê đủ cả 3 bản sao.

Đoạn bằng chứng: chỉ cần cho 6 câu nghị định giao thông, vì Điều 6 và Điều 7
NĐ 168/2024 bị chia 18 và 14 mảnh - lấy đúng Điều mà sai mảnh thì không có đáp
án. 36 câu còn lại, Điều cần tìm nằm gọn trong MỘT chunk ở mọi bản sao (đã đếm),
nên trúng Điều đã là trúng đoạn chứa đáp án.

Bộ này CỐ Ý gồm ba loại khó, vì bộ eval cũ 10 câu quá dễ (hit_rate 1.0 cho cả
hai embedder nên không phân biệt được gì):
  - lệch từ vựng: người hỏi dùng "hợp đồng", luật viết "giao dịch dân sự"
  - nêu đích danh số điều: dense embedding rất kém với token chính xác
  - dễ lẫn sang luật khác cùng chủ đề (dân sự / tố tụng dân sự / thi hành án dân sự)
"""

BLDS_2015 = frozenset({"91/2015/QH13", "Bo-luat-dan-su-2015-296215", "bo-luat-dan-su"})
BLHS_2015 = frozenset({"100/2015/QH13", "Bo-luat-hinh-su-2015-296661", "bo-luat-hinh-su"})
# Luật sửa đổi BLHS 2017 chứa NGUYÊN VĂN MỚI của Điều 9 và Điều 134 (chunk bắt
# đầu bằng "Điều 9. Phân loại tội phạm"), nên với hai điều này nó là nguồn đúng,
# thậm chí mới hơn. Khai báo tường minh chứ không để khớp tình cờ qua tên.
BLHS_SUA_DOI_2017 = frozenset({"12/2017/QH14"})
BLLD_2019 = frozenset({"45/2019/QH14", "Bo-Luat-lao-dong-2019-333670", "bo-luat-lao-dong"})
BLTTDS_2015 = frozenset({"92/2015/QH13", "Bo-luat-to-tung-dan-su-2015-296861",
                         "bo-luat-to-tung-dan-su"})
HNGD_2014 = frozenset({"52/2014/QH13", "Luat-Hon-nhan-va-gia-dinh-2014-238640",
                       "luat-hon-nhan-va-gia-dinh"})
ND168_2024 = frozenset({"congbao-43733"})

RETRIEVAL_QUESTIONS = [
    # --- lệch từ vựng ---
    {"question": "Hợp đồng vô hiệu khi nào?",
     "expected": [(BLDS_2015, 407)]},
    {"question": "Giao dịch dân sự vô hiệu trong trường hợp nào?",
     "expected": [(BLDS_2015, 122)]},
    {"question": "Muốn hợp đồng có giá trị pháp lý thì cần điều kiện gì?",
     "expected": [(BLDS_2015, 117)]},

    # --- nêu đích danh số điều (điểm yếu của dense, điểm mạnh của BM25) ---
    {"question": "Điều 117 Bộ luật Dân sự quy định gì?",
     "expected": [(BLDS_2015, 117)]},
    {"question": "Điều 630 Bộ luật Dân sự nói về vấn đề gì?",
     "expected": [(BLDS_2015, 630)]},
    {"question": "Nội dung Điều 9 Bộ luật Hình sự là gì?",
     "expected": [(BLHS_2015, 9), (BLHS_SUA_DOI_2017, 9)]},
    {"question": "Điều 105 Bộ luật Lao động quy định thế nào?",
     "expected": [(BLLD_2019, 105)]},

    # --- câu hỏi thường ---
    {"question": "Tuổi kết hôn tối thiểu theo luật Việt Nam là bao nhiêu?",
     "expected": [(HNGD_2014, 8)]},
    {"question": "Ai có quyền yêu cầu ly hôn?",
     "expected": [(HNGD_2014, 51)]},
    {"question": "Di chúc thế nào thì được coi là hợp pháp?",
     "expected": [(BLDS_2015, 630)]},
    {"question": "Thời hiệu thừa kế là bao lâu?",
     "expected": [(BLDS_2015, 623)]},
    {"question": "Thời hiệu khởi kiện tranh chấp hợp đồng là mấy năm?",
     "expected": [(BLDS_2015, 429)]},
    {"question": "Khi nào phát sinh trách nhiệm bồi thường thiệt hại ngoài hợp đồng?",
     "expected": [(BLDS_2015, 584)]},
    {"question": "Quyền sở hữu gồm những quyền gì?",
     "expected": [(BLDS_2015, 158)]},
    {"question": "Lãi suất cho vay tối đa được pháp luật quy định ra sao?",
     "expected": [(BLDS_2015, 468)]},
    {"question": "Tội phạm được phân loại như thế nào?",
     "expected": [(BLHS_2015, 9), (BLHS_SUA_DOI_2017, 9)]},
    {"question": "Bao nhiêu tuổi thì phải chịu trách nhiệm hình sự?",
     "expected": [(BLHS_2015, 12)]},
    {"question": "Hình phạt tù có thời hạn tối đa bao nhiêu năm?",
     "expected": [(BLHS_2015, 38)]},
    {"question": "Hợp đồng lao động bị vô hiệu trong trường hợp nào?",
     "expected": [(BLLD_2019, 49)]},
    {"question": "Thời giờ làm việc bình thường của người lao động là bao nhiêu?",
     "expected": [(BLLD_2019, 105)]},
    {"question": "Hợp đồng lao động chấm dứt trong những trường hợp nào?",
     "expected": [(BLLD_2019, 34)]},

    # --- dễ lẫn sang luật khác cùng chủ đề ---
    {"question": "Thời hiệu khởi kiện vụ án dân sự tại toà án được tính thế nào?",
     "expected": [(BLTTDS_2015, 184)]},
]


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
    {"question": "Ô tô vượt đèn đỏ bị phạt bao nhiêu tiền?",  # khoản 9
     "expected": [(ND168_2024, 6, ("18.000.000 đồng đến 20.000.000 đồng",
                                  "không chấp hành hiệu lệnh của đèn tín hiệu giao thông"))]},
    {"question": "Xe máy vượt đèn đỏ phạt bao nhiêu?",  # khoản 7
     "expected": [(ND168_2024, 7, ("4.000.000 đồng đến 6.000.000 đồng",
                                  "không chấp hành hiệu lệnh của đèn tín hiệu giao thông"))]},
    {"question": "Đi xe máy không đội mũ bảo hiểm bị phạt nhiêu tiền?",  # khoản 2
     "expected": [(ND168_2024, 7, ("400.000 đồng đến 600.000 đồng",
                                  "không đội mũ bảo hiểm cho người đi mô tô, xe máy"))]},
    {"question": "Uống rượu bia lái ô tô bị phạt thế nào?",  # khoản 6, 9 hoặc 11
     "expected": [(ND168_2024, 6, ("trong máu hoặc hơi thở có nồng độ cồn",))]},
    {"question": "Nhậu xong chạy xe máy bị phạt bao nhiêu?",  # khoản 6, 8 hoặc 9
     "expected": [(ND168_2024, 7, ("trong máu hoặc hơi thở có nồng độ cồn",))]},
    {"question": "Ô tô chạy quá tốc độ trên 35 km/h phạt bao nhiêu?",  # khoản 7
     "expected": [(ND168_2024, 6, ("12.000.000 đồng đến 14.000.000 đồng",
                                  "chạy quá tốc độ quy định trên 35 km/h"))]},

    # --- lao động ---
    {"question": "Một năm được nghỉ phép mấy ngày?",
     "expected": [(BLLD_2019, 113)]},
    {"question": "Tăng ca thì được trả thêm bao nhiêu phần trăm lương?",
     "expected": [(BLLD_2019, 98)]},
    {"question": "Công ty đuổi việc nhân viên trong trường hợp nào?",
     "expected": [(BLLD_2019, 125)]},
    {"question": "Thử việc được bao lâu thì phải ký hợp đồng chính thức?",
     "expected": [(BLLD_2019, 25)]},
    {"question": "Lương thử việc thấp nhất là bao nhiêu?",
     "expected": [(BLLD_2019, 26)]},

    # --- hôn nhân gia đình ---
    {"question": "Ly hôn thì chia tài sản ra sao?",
     "expected": [(HNGD_2014, 59)]},
    {"question": "Bỏ nhau rồi ai được quyền nuôi con?",
     "expected": [(HNGD_2014, 81)]},

    # --- hình sự: tên tội danh đời thường khác hẳn tên tội danh trong luật ---
    {"question": "Ăn trộm đồ thì bị tội gì?",
     "expected": [(BLHS_2015, 173)]},
    {"question": "Đánh người gây thương tích bị xử lý thế nào?",
     "expected": [(BLHS_2015, 134), (BLHS_SUA_DOI_2017, 134)]},
    {"question": "Lừa tiền người khác bị phạt tù bao nhiêu năm?",
     "expected": [(BLHS_2015, 174)]},
    {"question": "Trốn thuế bao nhiêu thì bị đi tù?",
     "expected": [(BLHS_2015, 200)]},

    # --- dân sự ---
    {"question": "Cho vay lãi bao nhiêu thì bị coi là cho vay nặng lãi?",
     "expected": [(BLDS_2015, 468)]},
    {"question": "Đặt cọc mua nhà rồi đổi ý thì có mất cọc không?",
     "expected": [(BLDS_2015, 328)]},
    {"question": "Làm hư đồ của người khác thì phải đền không?",
     "expected": [(BLDS_2015, 584)]},
]

# Dùng khi muốn một con số chung cho cả hai loại câu hỏi.
ALL_QUESTIONS = RETRIEVAL_QUESTIONS + COLLOQUIAL_QUESTIONS

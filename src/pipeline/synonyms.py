"""Nối thuật ngữ pháp lý vào truy vấn viết bằng lời nói đời thường.

Bài toán đo được: người hỏi "ô tô vượt đèn đỏ phạt bao nhiêu", luật viết "không
chấp hành hiệu lệnh của đèn tín hiệu giao thông". Hai cách nói cùng một việc
nhưng không chia sẻ một từ nào, nên vector của câu hỏi nằm xa vector của điều
luật. Đo trên 20 câu đời thường: MRR 0,4408 so với 0,5508 của bộ câu cũ, và ba
câu trượt hẳn khỏi top-15 (hạng 27, 36, ngoài 50).

Cách làm: NỐI THÊM chứ không thay thế. Câu hỏi gốc giữ nguyên trong truy vấn,
thuật ngữ luật được thêm vào sau. Thay thế hẳn là đánh cược rằng từ điển luôn
đúng; nối thêm thì trường hợp xấu nhất chỉ là truy vấn dài hơn một chút.

Giới hạn phải nói thẳng: đây là từ điển viết tay, chỉ phủ những cách nói thường
gặp nhất. Nó KHÔNG tổng quát hoá sang lĩnh vực chưa liệt kê. Đây là bản vá có
chủ đích cho một điểm yếu đã đo, không phải lời giải cho bài toán khoảng cách
từ vựng nói chung - lời giải đó cần huấn luyện lại mô hình nhúng trên cặp
(câu hỏi đời thường, điều luật) của tiếng Việt, ngoài phạm vi đồ án này.
"""
import re

# Mỗi mục: cách nói đời thường -> thuật ngữ luật dùng trong văn bản.
# Cụm bên phải đã kiểm là có thật trong kho, không viết theo trí nhớ.
_TU_DIEN = {
    # giao thông
    "vượt đèn đỏ": "không chấp hành hiệu lệnh của đèn tín hiệu giao thông",
    "vượt đèn vàng": "không chấp hành hiệu lệnh của đèn tín hiệu giao thông",
    "nhậu": "trong máu hoặc hơi thở có nồng độ cồn",
    "uống rượu": "trong máu hoặc hơi thở có nồng độ cồn",
    "uống bia": "trong máu hoặc hơi thở có nồng độ cồn",
    "rượu bia": "trong máu hoặc hơi thở có nồng độ cồn",
    "say xỉn": "trong máu hoặc hơi thở có nồng độ cồn",
    "chạy quá tốc độ": "điều khiển xe chạy quá tốc độ quy định",
    "phóng nhanh": "điều khiển xe chạy quá tốc độ quy định",
    "lấn làn": "không đi đúng phần đường, làn đường quy định",
    "đi ngược chiều": "đi ngược chiều của đường một chiều",
    "bằng lái": "giấy phép lái xe",
    "xe không chính chủ": "không làm thủ tục đăng ký sang tên xe",

    # hình sự: tên tội danh đời thường khác hẳn tên tội danh trong luật
    "ăn trộm": "tội trộm cắp tài sản",
    "ăn cắp": "tội trộm cắp tài sản",
    "trộm đồ": "tội trộm cắp tài sản",
    "đánh người": "tội cố ý gây thương tích hoặc gây tổn hại cho sức khỏe",
    "đánh nhau": "tội cố ý gây thương tích hoặc gây tổn hại cho sức khỏe",
    "lừa tiền": "tội lừa đảo chiếm đoạt tài sản",
    "lừa đảo": "tội lừa đảo chiếm đoạt tài sản",
    "quỵt tiền": "tội lạm dụng tín nhiệm chiếm đoạt tài sản",
    "trốn thuế": "tội trốn thuế",

    # lao động
    "nghỉ phép": "nghỉ hằng năm",
    "tăng ca": "tiền lương làm thêm giờ",
    "làm thêm": "tiền lương làm thêm giờ",
    "đuổi việc": "xử lý kỷ luật sa thải",
    "sa thải": "xử lý kỷ luật sa thải",
    "nghỉ đẻ": "nghỉ thai sản",

    # dân sự
    "làm hư": "bồi thường thiệt hại về tài sản",
    "làm hỏng": "bồi thường thiệt hại về tài sản",
    "làm mất đồ": "bồi thường thiệt hại về tài sản",
    "phải đền": "trách nhiệm bồi thường thiệt hại",
    "cho vay nặng lãi": "lãi suất vay do các bên thỏa thuận",
    "mất cọc": "đặt cọc để bảo đảm giao kết hợp đồng",
    "tiền cọc": "đặt cọc để bảo đảm giao kết hợp đồng",

    # hôn nhân gia đình
    "bỏ nhau": "ly hôn",
    "quyền nuôi con": "trông nom, chăm sóc, nuôi dưỡng, giáo dục con sau khi ly hôn",
    "chia tài sản": "nguyên tắc giải quyết tài sản của vợ chồng khi ly hôn",
}

# Nối tối đa ngần này thuật ngữ. Một câu hỏi chạm nhiều mục thì phần thêm vào
# sẽ dài hơn cả câu hỏi và át mất chủ đề thật - đúng lỗi đã gặp khi thử ghép
# nguyên câu hỏi trước vào câu nối tiếp.
MAX_THEM = 2


def expand_query(question: str) -> str:
    """Trả về câu hỏi kèm thuật ngữ luật tương ứng, hoặc nguyên văn nếu không khớp."""
    thap = question.lower()
    them = []
    for doi_thuong, phap_ly in _TU_DIEN.items():
        if doi_thuong in thap and phap_ly not in thap and phap_ly not in them:
            them.append(phap_ly)
            if len(them) == MAX_THEM:
                break
    return question + " " + " ".join(them) if them else question


def matched_terms(question: str) -> list:
    """Các thuật ngữ sẽ được nối thêm. Tách riêng để test và để soi lỗi."""
    q = expand_query(question)
    return [] if q == question else q[len(question) + 1:].split("  ")

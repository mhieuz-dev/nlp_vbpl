"""Bộ câu nghiệm thu: đo cả truy xuất lẫn câu trả lời và hành vi.

Khác `retrieval_dataset.py` (chỉ chấm truy xuất): mỗi câu ở đây có `kind` nói
hệ thống PHẢI làm gì:
- "answer": trả lời, trích đúng nguồn, có đủ chi tiết mấu chốt `must_contain`
  (mỗi phần tử là một nhóm cách viết tương đương, chỉ cần khớp một).
- "clarify": mức phạt đổi theo dữ kiện câu hỏi chưa nêu (loại xe...), phải hỏi lại.
- "abstain": kho không có căn cứ, phải từ chối hoặc ghi rõ phần chưa tìm thấy.

`split`: "dev" được dùng khi chỉnh hệ thống; "holdout" CHỈ để chấm lần cuối,
không được nhìn vào kết quả từng câu của nó để sửa prompt, từ điển hay truy
xuất - nhìn vào là nó thành dev, và con số nghiệm thu thành điểm học tủ.

Ground truth đã đối chiếu nguyên văn trong kho ngày 29/09/2026. Câu không trả
lời được chọn theo chủ đề KHÔNG xuất hiện ở bất kỳ đoạn nào (so bỏ dấu: tên văn
bản UTS_VLC viết không dấu, tra có dấu sẽ tưởng kho thiếu Luật BHXH trong khi
kho có - lỗi đã mắc ngày 29/09).
"""
from evaluation.retrieval_dataset import (BLDS_2015, BLHS_2015, BLLD_2019, HNGD_2014,
                                          ND168_2024)

# Luật BHXH đang áp dụng: VBHN 19/VBHN-VPQH (12/02/2026) hợp nhất Luật BHXH
# 41/2024/QH15, nạp từ Công báo ngày 03/10. Trước đó kho chỉ có bản 2014 và
# 2006, nên app trả lời "20 năm" theo luật đã hết hiệu lực.
BHXH_HIEN_HANH = frozenset({"congbao-468972"})

ACCEPTANCE = [
    # ===== dev =====
    {"id": "ly-hon-don-phuong", "split": "dev", "kind": "answer",
     "question": "Ly hôn đơn phương cần điều kiện gì?",
     "expected": [(HNGD_2014, 56)],
     "must_contain": [["bạo lực gia đình"]]},
    {"id": "bao-truoc-nghi-viec", "split": "dev", "kind": "answer",
     "question": "Muốn nghỉ việc thì phải báo trước cho công ty bao nhiêu ngày?",
     "expected": [(BLLD_2019, 35)],
     "must_contain": [["45 ngày", "bốn mươi lăm ngày"]]},
    {"id": "nghi-thai-san", "split": "dev", "kind": "answer",
     "question": "Lao động nữ được nghỉ thai sản bao lâu?",
     "expected": [(BLLD_2019, 139)],
     "must_contain": [["06 tháng", "6 tháng", "sáu tháng"]]},
    {"id": "nguoi-chua-thanh-nien", "split": "dev", "kind": "answer",
     "question": "Người chưa thành niên là người bao nhiêu tuổi?",
     "expected": [(BLDS_2015, 21)],
     "must_contain": [["mười tám tuổi", "18 tuổi"]]},
    {"id": "muon-tien-bo-tron", "split": "dev", "kind": "answer",
     "question": "Mượn tiền rồi bỏ trốn không trả thì có bị đi tù không?",
     "expected": [(BLHS_2015, 175)],
     "must_contain": []},
    {"id": "lam-them-gio-thang", "split": "dev", "kind": "answer",
     "question": "Sếp bắt làm thêm giờ thì mỗi tháng tối đa được bao nhiêu giờ?",
     "expected": [(BLLD_2019, 107)],
     "must_contain": [["40 giờ", "bốn mươi giờ"]]},
    {"id": "den-do-chung-chung", "split": "dev", "kind": "clarify",
     "question": "Vượt đèn đỏ bị phạt bao nhiêu?",
     "expected": [(ND168_2024, 6, ["đèn tín hiệu"]), (ND168_2024, 7, ["đèn tín hiệu"])],
     "must_contain": []},
    {"id": "ruou-bia-chung-chung", "split": "dev", "kind": "clarify",
     "question": "Uống rượu bia rồi lái xe thì bị phạt bao nhiêu?",
     "expected": [(ND168_2024, 6, ["nồng độ cồn"]), (ND168_2024, 7, ["nồng độ cồn"])],
     "must_contain": []},
    {"id": "nau-pho", "split": "dev", "kind": "abstain",
     "question": "Cách nấu phở bò ngon?",
     "expected": [], "must_contain": []},
    {"id": "bhxh-luong-huu", "split": "dev", "kind": "answer",
     "question": "Đóng bảo hiểm xã hội bao nhiêu năm thì được nhận lương hưu?",
     # Điều 64: BHXH bắt buộc; Điều 98: tự nguyện. Cả hai đều "từ đủ 15 năm".
     "expected": [(BHXH_HIEN_HANH, 64), (BHXH_HIEN_HANH, 98)],
     "must_contain": [["15 năm", "mười lăm năm"]]},
    {"id": "noi-tiep-o-to", "split": "dev", "kind": "answer",
     "history": [
         {"role": "user", "content": "Xe máy vượt đèn đỏ phạt bao nhiêu?"},
         {"role": "assistant", "content": "Người điều khiển xe mô tô, xe gắn máy "
          "không chấp hành hiệu lệnh của đèn tín hiệu giao thông bị phạt tiền "
          "từ 4.000.000 đồng đến 6.000.000 đồng [1]."},
     ],
     "question": "Còn ô tô thì sao?",
     "expected": [(ND168_2024, 6, ["đèn tín hiệu"])],
     "must_contain": [["18.000.000", "18 triệu"]]},
    {"id": "noi-tiep-tuoi-ket-hon-nu", "split": "dev", "kind": "answer",
     "history": [
         {"role": "user", "content": "Nam bao nhiêu tuổi thì được kết hôn?"},
         {"role": "assistant", "content": "Nam phải từ đủ 20 tuổi trở lên [1]."},
     ],
     "question": "Còn nữ thì sao?",
     "expected": [(HNGD_2014, 8)],
     "must_contain": [["18 tuổi", "mười tám tuổi"]]},

    {"id": "noi-tiep-nld-khong-bao-truoc", "split": "dev", "kind": "answer",
     "history": [
         {"role": "user", "content": "Người lao động đơn phương chấm dứt hợp đồng "
          "phải báo trước bao nhiêu ngày?"},
         {"role": "assistant", "content": "Ít nhất 45 ngày với hợp đồng không xác "
          "định thời hạn, 30 ngày với hợp đồng từ 12 đến 36 tháng [1]."},
     ],
     "question": "Nếu người lao động ấy không báo trước thì phải bồi thường gì không?",
     "expected": [(BLLD_2019, 40)],
     "must_contain": [["nửa tháng tiền lương"]]},
    # Chuyển từ holdout sang 03/10: đã nhìn vào chỗ trượt của câu này (đại từ
    # "người đó" không được nhận là câu nối tiếp) để sửa followup.py, nên nó
    # không còn là câu giữ riêng. Câu noi-tiep-tai-san-ly-hon thay chỗ nó.
    {"id": "noi-tiep-trom-15-tuoi", "split": "dev", "kind": "answer",
     "history": [
         {"role": "user", "content": "Trộm cắp tài sản bị phạt tù bao nhiêu năm?"},
         {"role": "assistant", "content": "Tuỳ giá trị tài sản và tình tiết, từ "
          "cải tạo không giam giữ đến 20 năm tù [1]."},
     ],
     "question": "Nếu người đó mới 15 tuổi thì có bị truy cứu không?",
     "expected": [(BLHS_2015, 12)],
     "must_contain": []},

    # ===== holdout: chỉ chấm, không chỉnh theo =====
    {"id": "tuoi-nghi-huu-nam", "split": "holdout", "kind": "answer",
     "question": "Tuổi nghỉ hưu của lao động nam là bao nhiêu?",
     "expected": [(BLLD_2019, 169)],
     "must_contain": [["62 tuổi", "sáu mươi hai tuổi"]]},
    {"id": "the-chap", "split": "holdout", "kind": "answer",
     "question": "Thế chấp tài sản là gì?",
     "expected": [(BLDS_2015, 317)],
     "must_contain": [["không giao tài sản", "không phải giao tài sản",
                       "không chuyển giao tài sản"]]},
    {"id": "dien-thoai-xe-may", "split": "holdout", "kind": "answer",
     "question": "Đi xe máy mà dùng điện thoại thì bị phạt thế nào?",
     "expected": [(ND168_2024, 7, ["điện thoại"])],
     "must_contain": []},
    {"id": "phat-vi-pham-hop-dong", "split": "holdout", "kind": "answer",
     "question": "Hai bên có được thoả thuận phạt vi phạm trong hợp đồng không?",
     "expected": [(BLDS_2015, 418)],
     "must_contain": []},
    {"id": "cho-nghi-trai-luat", "split": "holdout", "kind": "answer",
     "question": "Bị công ty cho nghỉ việc trái luật thì công ty phải làm gì?",
     "expected": [(BLLD_2019, 41)],
     "must_contain": [["trở lại làm việc", "nhận lại", "nhận người lao động trở lại"]]},
    {"id": "qua-toc-do-chung-chung", "split": "holdout", "kind": "clarify",
     "question": "Chạy quá tốc độ bị phạt bao nhiêu?",
     "expected": [(ND168_2024, 6, ["tốc độ"]), (ND168_2024, 7, ["tốc độ"])],
     "must_contain": []},
    {"id": "khong-bang-lai", "split": "holdout", "kind": "clarify",
     "question": "Không có bằng lái thì bị phạt bao nhiêu?",
     "expected": [(ND168_2024, 18, ["giấy phép lái xe"])],
     "must_contain": []},
    {"id": "gia-vang", "split": "holdout", "kind": "abstain",
     "question": "Giá vàng SJC hôm nay bao nhiêu?",
     "expected": [], "must_contain": []},
    {"id": "thue-bitcoin", "split": "holdout", "kind": "abstain",
     "question": "Mua bán bitcoin ở Việt Nam thì bị đánh thuế bao nhiêu phần trăm?",
     "expected": [], "must_contain": []},
    {"id": "noi-tiep-luong-thu-viec", "split": "holdout", "kind": "answer",
     "history": [
         {"role": "user", "content": "Thời gian thử việc tối đa là bao lâu?"},
         {"role": "assistant", "content": "Không quá 180 ngày với công việc quản lý "
          "doanh nghiệp, 60 ngày với công việc cần trình độ cao đẳng trở lên [1]."},
     ],
     "question": "Lương trong thời gian đó ít nhất là bao nhiêu?",
     "expected": [(BLLD_2019, 26)],
     "must_contain": [["85%", "85 phần trăm"]]},
    {"id": "noi-tiep-tai-san-ly-hon", "split": "holdout", "kind": "answer",
     "history": [
         {"role": "user", "content": "Tài sản chung của vợ chồng gồm những gì?"},
         {"role": "assistant", "content": "Gồm tài sản do vợ, chồng tạo ra, thu nhập "
          "do lao động, sản xuất, kinh doanh trong thời kỳ hôn nhân [1]."},
     ],
     "question": "Khi ly hôn thì tài sản ấy được chia theo nguyên tắc nào?",
     "expected": [(HNGD_2014, 59)],
     "must_contain": [["chia đôi"]]},
]

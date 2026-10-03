"""Quan hệ sửa đổi/thay thế đã xác minh cho các văn bản dùng trong bộ đánh giá và demo.

Kho không có trường nào nói văn bản nào sửa văn bản nào, nên danh sách này viết
tay và CHỈ ghi điều đọc được trong chính nội dung văn bản ở kho (xác minh
29/09/2026, Luật BHXH 03/10/2026, `basis` là điều chứa câu đó). Văn bản không có trong danh sách thì
giao diện ghi "chưa xác định", không đoán.

Chỉ biết những gì nằm trong kho: một văn bản có thể đã bị sửa bởi văn bản ra
sau mà kho không có, nên đây không phải căn cứ để nói văn bản "còn hiệu lực".
"""

RELATIONS = [
    {
        "doc_ids": {"91/2015/QH13", "Bo-luat-dan-su-2015-296215", "bo-luat-dan-su"},
        "relations": [{
            "text": "Thay thế Bộ luật dân sự số 33/2005/QH11",
            "basis": "Điều 689 Bộ luật dân sự 2015",
        }],
    },
    {
        "doc_ids": {"100/2015/QH13", "Bo-luat-hinh-su-2015-296661", "bo-luat-hinh-su"},
        "relations": [
            {
                "text": "Thay thế Bộ luật hình sự số 15/1999/QH10 và Luật số 37/2009/QH12",
                "basis": "Điều 426 Bộ luật hình sự 2015",
            },
            {
                "text": "Được sửa đổi, bổ sung, bãi bỏ một số điều bởi Luật số 12/2017/QH14 "
                        "(hiệu lực 01/01/2018)",
                "basis": "Điều 1 và Điều 3 Luật số 12/2017/QH14",
            },
        ],
    },
    {
        "doc_ids": {"12/2017/QH14"},
        "relations": [{
            "text": "Sửa đổi, bổ sung, bãi bỏ một số điều của Bộ luật hình sự số 100/2015/QH13",
            "basis": "Điều 1 Luật số 12/2017/QH14",
        }],
    },
    {
        "doc_ids": {"45/2019/QH14", "Bo-Luat-lao-dong-2019-333670", "bo-luat-lao-dong"},
        "relations": [{
            "text": "Thay thế Bộ luật lao động số 10/2012/QH13",
            "basis": "Điều 220 Bộ luật lao động 2019",
        }],
    },
    {
        "doc_ids": {"92/2015/QH13", "Bo-luat-to-tung-dan-su-2015-296861",
                    "bo-luat-to-tung-dan-su"},
        "relations": [{
            "text": "Thay thế Bộ luật tố tụng dân sự số 24/2004/QH11 "
                    "(đã sửa đổi theo Luật số 65/2011/QH12), trừ một số quy định",
            "basis": "Điều 517 Bộ luật tố tụng dân sự 2015",
        }],
    },
    {
        "doc_ids": {"52/2014/QH13", "Luat-Hon-nhan-va-gia-dinh-2014-238640",
                    "luat-hon-nhan-va-gia-dinh"},
        "relations": [{
            "text": "Thay thế Luật hôn nhân và gia đình số 22/2000/QH10",
            "basis": "Điều 132 Luật hôn nhân và gia đình 2014",
        }],
    },
    {
        # Điều 52 sửa đổi, bổ sung và bãi bỏ TỪNG PHẦN NĐ 100/2019, không thay
        # thế cả văn bản: phần NĐ 100 không bị bãi bỏ (ví dụ đường sắt) vẫn còn.
        "doc_ids": {"congbao-43733"},
        "relations": [{
            "text": "Sửa đổi, bổ sung và bãi bỏ một phần Nghị định số 100/2019/NĐ-CP "
                    "(đã sửa đổi theo Nghị định số 123/2021/NĐ-CP)",
            "basis": "Điều 52 Nghị định số 168/2024/NĐ-CP",
        }],
    },
]

# Luật BHXH: kho có hai bản của Luật 58/2014 (nạp từ UTS_VLC) và VBHN
# 19/VBHN-VPQH hợp nhất Luật 41/2024/QH15 (Công báo, nạp 03/10/2026).
_BHXH_CU = {"Luat-Bao-hiem-xa-hoi-2014-259700", "luat-bao-hiem-xa-hoi"}
_BHXH_MOI = "congbao-468972"
_BHXH_CAN_CU = "Điều 140 Luật Bảo hiểm xã hội số 41/2024/QH15"
RELATIONS += [
    {
        "doc_ids": {_BHXH_MOI},
        "relations": [{
            "text": "Hợp nhất Luật Bảo hiểm xã hội số 41/2024/QH15 (hiệu lực 01/07/2025), "
                    "thay thế Luật Bảo hiểm xã hội số 58/2014/QH13",
            "basis": _BHXH_CAN_CU,
        }],
    },
    {
        "doc_ids": _BHXH_CU,
        "relations": [{
            "text": "Hết hiệu lực từ 01/07/2025, thay bằng Luật Bảo hiểm xã hội số 41/2024/QH15",
            "basis": _BHXH_CAN_CU,
        }],
    },
]

# Văn bản bị thay thế TOÀN BỘ -> văn bản thay thế, cả hai cùng có trong kho.
# Truy xuất bỏ văn bản cũ đi (src/vectorstore/store.py): để cả hai thì model
# trộn hai bản, đo thật 03/10 trả "BHXH bắt buộc đủ 20 năm" theo luật 2014 đã
# hết hiệu lực. Chỉ ghi văn bản bị thay thế toàn bộ đã xác minh bằng điều luật;
# sửa đổi một phần (như NĐ 168 với NĐ 100) KHÔNG thuộc danh sách này.
SUPERSEDED = {cu: _BHXH_MOI for cu in _BHXH_CU}

_BY_ID = {doc_id: entry["relations"] for entry in RELATIONS for doc_id in entry["doc_ids"]}


def relations_for(doc_id: str) -> list[dict]:
    """[{text, basis}] đã xác minh của văn bản, rỗng nếu chưa xác minh."""
    return list(_BY_ID.get(doc_id, []))

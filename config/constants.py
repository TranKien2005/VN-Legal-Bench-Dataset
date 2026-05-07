"""
Constants cho dự án VN-Legal-Bench-Dataset.
"""

# 15 nhãn vấn đề pháp lý chính kèm mô tả chi tiết (Chuẩn hóa theo yêu cầu người dùng)
LEGAL_ISSUE_LABELS = [
    {
        "label": "Hôn nhân và Gia đình",
        "description": "Điều chỉnh các quan hệ nhân thân và tài sản giữa các thành viên trong gia đình (vợ chồng, cha mẹ con cái, ông bà cháu)."
    },
    {
        "label": "Giao thông và Vận tải",
        "description": "Các quy tắc di chuyển trên đường bộ, đường thủy, đường hàng không và chế tài khi vi phạm."
    },
    {
        "label": "Thuế, Phí và Lệ phí",
        "description": "Các nghĩa vụ nộp tiền vào ngân sách nhà nước phát sinh từ thu nhập, tài sản hoặc dịch vụ công."
    },
    {
        "label": "Đất đai và Nhà ở",
        "description": "Quyền quản lý, sử dụng đất, sở hữu nhà ở và các giao dịch liên quan đến bất động sản."
    },
    {
        "label": "Lao động và Bảo hiểm xã hội",
        "description": "Mối quan hệ giữa người lao động và người sử dụng lao động dựa trên hợp đồng lao động."
    },
    {
        "label": "Kinh doanh, đầu tư, thương mại",
        "description": "Các hoạt động nhằm mục đích sinh lợi của thương nhân và các vấn đề nội bộ công ty."
    },
    {
        "label": "Tài chính, vay nợ, tín dụng",
        "description": "Các giao dịch tài chính chuyên biệt với các tổ chức tín dụng và doanh nghiệp bảo hiểm."
    },
    {
        "label": "Sở hữu trí tuệ",
        "description": "Bảo hộ các sản phẩm của trí tuệ con người (logo, sáng chế, tác phẩm nghệ thuật)."
    },
    {
        "label": "Môi trường và Tài nguyên",
        "description": "Khai thác khoáng sản, nguồn nước và các hành vi gây ô nhiễm."
    },
    {
        "label": "An ninh quốc gia, trật tự, An toàn xã hội và tệ nạn xã hội",
        "description": "Các hành vi gây mất an ninh công cộng, tệ nạn xã hội và tội phạm ma túy."
    },
    {
        "label": "Quyền con người",
        "description": "Các hành vi trực tiếp gây tổn hại đến thân thể, tính mạng, danh dự và nhân phẩm."
    },
    {
        "label": "Quyền sở hữu tài sản",
        "description": "Các hành vi chiếm đoạt, hủy hoại tài sản của người khác ngoài phạm vi hợp đồng (trộm, cướp, lừa đảo chiếm đoạt tài sản)."
    },
    {
        "label": "Hành chính, dịch vụ công, an sinh",
        "description": "Khiếu nại, khởi kiện các quyết định hoặc hành vi hành chính của cơ quan nhà nước."
    },
    {
        "label": "Tư pháp và Tố tụng",
        "description": "Các quy định về cách thức nộp đơn, thời hạn khởi kiện, thẩm quyền của tòa án và thi hành án."
    },
    {
        "label": "Các vấn đề pháp lý khác",
        "description": "Hỗn hợp hoặc các lĩnh vực đặc thù khác không nằm trong 14 nhóm trên."
    }
]

# Loại văn bản quy phạm pháp luật
DOC_TYPES = [
    "Hiến pháp",
    "Luật",
    "Pháp lệnh",
    "Nghị định",
    "Nghị quyết",
    "Thông tư",
    "Quyết định",
    "Chỉ thị",
]

# Keywords để tách các phần trong bản án
CASE_SECTION_KEYWORDS = {
    "case_content": "NỘI DUNG VỤ ÁN",
    "court_reasoning": "NHẬN ĐỊNH CỦA TÒA ÁN",
    "decision": "QUYẾT ĐỊNH",
}

# 5 loại vai trò lập luận (Dành cho các task phân tích lập luận)
ARGUMENT_ROLES = [
    "Tóm tắt sự việc",
    "Dẫn chiếu căn cứ",
    "Bác bỏ/Chấp nhận lập luận",
    "Lập luận bắc cầu",
    "Kết luận logic",
]

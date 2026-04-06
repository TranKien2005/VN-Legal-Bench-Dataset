"""
Constants cho dự án VN-Legal-Bench-Dataset.
"""

# 15 nhãn vấn đề pháp lý chính (Issue Spotting)
LEGAL_ISSUE_LABELS = [
    "Hôn nhân và Gia đình",
    "Giao thông và Vận tải",
    "Thuế, Phí và Lệ phí",
    "Đất đai và Nhà ở",
    "Lao động và Bảo hiểm xã hội",
    "Kinh doanh và Đầu tư",
    "Ngân hàng, Tín dụng và Bảo hiểm",
    "Sở hữu trí tuệ",
    "Môi trường và Tài nguyên",
    "Trật tự, An toàn xã hội và Ma túy",
    "Xâm phạm Quyền con người",
    "Xâm phạm Quyền sở hữu tài sản",
    "Hành chính và Quản lý nhà nước",
    "Tư pháp và Tố tụng",
    "Các vấn đề pháp lý khác",
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

# 6 loại vai trò lập luận (Task 5.1)
ARGUMENT_ROLES = [
    "Tóm tắt sự việc",
    "Dẫn chiếu căn cứ",
    "Bác bỏ/Chấp nhận lập luận",
    "Lập luận bắc cầu",
    "Kết luận logic",
]

"""
Constants cho dự án VN-Legal-Bench-Dataset.
"""

# 15 nhãn vấn đề pháp lý chính kèm mô tả chi tiết (Chuẩn hóa theo yêu cầu người dùng)
LEGAL_ISSUE_LABELS = [
    {
        "label": "Hôn nhân và Gia đình",
        "description": "Ly hôn, kết hôn, quan hệ vợ chồng, cha mẹ con, nuôi con, cấp dưỡng, giám hộ, chia tài sản chung vợ chồng và các quyền, nghĩa vụ phát sinh trong gia đình."
    },
    {
        "label": "Giao thông và Vận tải",
        "description": "Vi phạm quy tắc giao thông, tai nạn giao thông, điều kiện điều khiển phương tiện, vận tải đường bộ, đường thủy, hàng không và trách nhiệm phát sinh từ hoạt động giao thông vận tải."
    },
    {
        "label": "Thuế, Phí và Lệ phí",
        "description": "Các nghĩa vụ nộp tiền vào ngân sách nhà nước phát sinh từ thu nhập, tài sản hoặc dịch vụ công."
    },
    {
        "label": "Đất đai và Nhà ở",
        "description": "Quyền sử dụng đất, quyền sở hữu nhà ở, cấp hoặc hủy giấy chứng nhận, ranh giới đất, thu hồi đất, bồi thường hỗ trợ tái định cư, chuyển nhượng/tặng cho/thừa kế nhà đất khi trọng tâm là quyền về đất hoặc nhà ở."
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
        "description": "Quyền tác giả, quyền liên quan, nhãn hiệu, sáng chế, kiểu dáng công nghiệp, bí mật kinh doanh, chuyển giao quyền sở hữu trí tuệ và hành vi xâm phạm quyền sở hữu trí tuệ."
    },
    {
        "label": "Môi trường và Tài nguyên",
        "description": "Bảo vệ môi trường, khai thác khoáng sản, nguồn nước, rừng, lâm sản, thủy sản, tài nguyên thiên nhiên và các hành vi gây ô nhiễm hoặc khai thác tài nguyên trái phép."
    },
    {
        "label": "Trật tự, An toàn xã hội và Ma túy",
        "description": "Ma túy, gây rối trật tự công cộng, đánh bạc, mại dâm, vũ khí vật liệu nổ, phòng cháy chữa cháy và các hành vi xâm phạm trật tự, an toàn công cộng."
    },
    {
        "label": "Xâm phạm tính mạng, sức khỏe, danh dự, nhân phẩm",
        "description": "Giết người, cố ý gây thương tích, vô ý làm chết người, làm nhục, vu khống, xâm hại tình dục, bắt giữ người trái pháp luật và các hành vi xâm phạm quyền nhân thân."
    },
    {
        "label": "Xâm phạm sở hữu tài sản",
        "description": "Trộm cắp, cướp, cướp giật, cưỡng đoạt, lừa đảo chiếm đoạt, lạm dụng tín nhiệm chiếm đoạt, hủy hoại hoặc cố ý làm hư hỏng tài sản ngoài phạm vi tranh chấp hợp đồng dân sự."
    },
    {
        "label": "Hành chính và Quản lý nhà nước",
        "description": "Khiếu kiện quyết định hoặc hành vi hành chính, xử phạt vi phạm hành chính, quản lý nhà nước, hộ tịch, cư trú, công chức, chính sách công và các biện pháp hành chính của cơ quan nhà nước."
    },
    {
        "label": "Tư pháp, Tố tụng và Thi hành án",
        "description": "Thẩm quyền, thời hiệu, trình tự thủ tục tố tụng, chứng cứ, án phí, kháng cáo, giám đốc thẩm, trọng tài, công chứng, thi hành án và các vấn đề mà trọng tâm là thủ tục giải quyết hoặc thi hành bản án; không chọn chỉ vì bản án có thông tin tố tụng thông thường."
    },
    {
        "label": "Dân sự, Hợp đồng và Nghĩa vụ",
        "description": "Giao dịch dân sự, hợp đồng đặt cọc, mua bán, vay mượn dân sự, thuê, mượn, gửi giữ, dịch vụ, bồi thường thiệt hại, giao dịch vô hiệu, đòi tài sản, thừa kế và nghĩa vụ dân sự không thuộc nhóm đất đai, tín dụng, lao động hoặc thương mại chuyên biệt."
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

TASK_IDS = [
    "task_1_1",
    "task_1_2",
    "task_2_1",
    "task_2_2",
    "task_2_3",
    "task_2_4",
    "task_2_6",
    "task_3_1",
]

MCQ_TASKS = {"task_1_2", "task_2_4", "task_2_6", "task_3_1"}
EXACT_RECALL_TASKS = {"task_2_1", "task_2_2", "task_2_3"}
MCQ_INSTRUCTION = (
    "Yêu cầu bắt buộc: Chỉ trả về một đáp án duy nhất. "
    "Nếu trả lời bằng chữ cái thì chỉ ghi A, B, C hoặc D, không kèm giải thích. "
    "Nếu trả lời bằng nội dung thì chỉ ghi nguyên văn nội dung của phương án đúng, không kèm chữ cái, không giải thích, không thêm câu dẫn."
)
EXACT_RECALL_INSTRUCTIONS = {
    "task_2_1": (
        "\n\nYêu cầu bắt buộc cho Task 2.1: Chỉ trả về phần định nghĩa/quy định được hỏi. "
        "Không viết tên văn bản, không viết số điều, không mở đầu bằng các cụm như 'Theo luật', 'Khái niệm này là'. "
        "Tuyệt đối không tóm tắt, không diễn giải lại, không bỏ ý, không thêm thông tin ngoài văn bản gốc."
    ),
    "task_2_2": (
        "\n\nYêu cầu bắt buộc cho Task 2.2: Chỉ trả về nội dung điều luật đã được hỏi theo đúng định dạng yêu cầu trong câu hỏi. "
        "Không xin lỗi, không nói không có dữ liệu, không hướng dẫn đi tra cứu, không viết thêm tên luật hoặc số điều nếu câu hỏi không yêu cầu. "
        "Tuyệt đối không tóm tắt, không diễn giải lại, không bỏ ý, không thêm thông tin ngoài văn bản gốc."
    ),
    "task_2_3": (
        "\n\nYêu cầu bắt buộc cho Task 2.3: Chỉ trả về đúng chuỗi thông tin được hỏi, không thêm bất kỳ chữ nào khác. "
        "Nếu hỏi số hiệu văn bản, chỉ trả về số hiệu, ví dụ: 33/2013/QH13; không viết 'Luật ... số 33/2013/QH13'. "
        "Nếu hỏi điều khoản, chỉ trả về theo mẫu: Điều [số điều] [số hiệu văn bản]. "
        "Nếu hỏi ngày hiệu lực, chỉ trả về ngày theo định dạng DD/MM/YYYY. "
        "Nếu hỏi người ký, chỉ trả về họ tên người ký, không thêm chức danh."
    ),
}


def render_options(options: list[str]) -> str:
    letters = "ABCD"
    return "\n".join(f"{letters[i]}. {option}" for i, option in enumerate(options))


def build_prompt(sample: dict, task_id: str) -> str:
    question = sample.get("question", "")
    options = sample.get("options") or []

    if task_id == "task_3_1":
        base = question
        if options:
            base += "\n\nCác phương án:\n" + render_options(options)
        return (
            f"{base}\n\n"
            "Hãy trả về duy nhất một JSON hợp lệ theo mẫu sau:\n"
            "{\"answer\": \"nội dung đáp án đúng\", "
            "\"explanation\": \"lời giải thích chi tiết\"}\n\n"
            "Trường answer phải khớp với một trong các phương án.\n"
            "Trường explanation phải viết rõ ràng theo cấu trúc lập luận pháp lý, không chỉ kết luận chung chung. "
            "Mỗi ý quan trọng nên đi theo mẫu: Căn cứ vào tình tiết vụ án cho thấy [fact cụ thể]; "
            "đồng thời căn cứ vào [điều luật/quy định/nguyên tắc pháp lý], có thể kết luận [kết luận pháp lý]. "
            "Nếu có tình tiết giảm nhẹ, tăng nặng, phân hóa vai trò hoặc nghĩa vụ, hãy nêu sau chữ 'Tuy nhiên' hoặc 'Đối với'.\n\n"
            "Yêu cầu explanation gồm 3-6 câu và phải có đủ:\n"
            "1. Ít nhất hai tình tiết cụ thể từ vụ án.\n"
            "2. Điều luật hoặc nguyên tắc pháp lý được áp dụng.\n"
            "3. Liên hệ trực tiếp giữa từng tình tiết và điều luật.\n"
            "4. Lý do vì sao chọn đúng kết quả trong answer, gồm mức án/nghĩa vụ/chấp nhận hoặc bác yêu cầu nếu có.\n\n"
            "Ví dụ phong cách giải thích tốt:\n"
            "Căn cứ vào tình tiết vụ án cho thấy bị cáo đã trực tiếp thực hiện hành vi bị cấm và hậu quả phát sinh thuộc phạm vi điều luật được viện dẫn; "
            "đồng thời căn cứ vào Điều X của luật liên quan, có thể kết luận hành vi của bị cáo cấu thành vi phạm/tội danh tương ứng. "
            "Căn cứ thêm vào vai trò của từng người trong vụ án, người khởi xướng hoặc thực hiện chính phải chịu trách nhiệm nặng hơn, còn người tham gia với vai trò thứ yếu được phân hóa trách nhiệm. "
            "Tuy nhiên, do có các tình tiết giảm nhẹ như thành khẩn khai báo, bồi thường hoặc nhân thân được Tòa án xem xét, mức xử lý được giảm nhẹ hoặc cho hưởng án treo/cải tạo không giam giữ nếu phù hợp."
        )

    if options:
        return (
            f"{question}\n\n"
            f"Các phương án:\n{render_options(options)}\n\n"
            f"{MCQ_INSTRUCTION}"
        )

    if task_id in EXACT_RECALL_TASKS:
        return question + EXACT_RECALL_INSTRUCTIONS[task_id]

    return question

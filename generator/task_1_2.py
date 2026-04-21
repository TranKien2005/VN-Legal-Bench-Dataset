import json
from pathlib import Path
from sqlalchemy.sql import func
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import CourtCase
from generator.llm_client import LLMClient

# Few-shot examples nhúng vào câu hỏi để mô hình được đánh giá hiểu format output
QUESTION_EXAMPLES = (
    "Ví dụ câu trả lời đúng:\n"
    "- 'Vấn đề xin ly hôn'\n"
    "- 'Vấn đề tranh chấp hợp đồng đặt cọc'\n"
    "- 'Vấn đề yêu cầu bồi thường thiệt hại ngoài hợp đồng'\n"
)

def generate_task_1_2(limit=50):
    """
    Task 1.2 — Core Issue Generation
    Mục tiêu: Xác định vấn đề pháp lý cốt lõi của tình huống.

    Ground truth: LLM chỉ đọc title bản án (title_web hoặc title_parsed)
                  → sinh cụm từ ngắn bắt đầu bằng 'Vấn đề'. Rất ít token.
    Câu hỏi: Cung cấp section_content + hướng dẫn + ví dụ → yêu cầu sinh vấn đề cốt lõi.
    """
    print(f"Starting Task 1.2 Generation (Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    cases = session.query(CourtCase).filter(
        CourtCase.section_content != None
    ).order_by(func.random()).limit(limit).all()

    benchmark_data = []

    # Few-shot examples dùng riêng để sinh ground truth (không cần trong GT prompt)
    gt_examples = (
        "Ví dụ:\n"
        "Tên bản án: Tranh chấp hợp đồng chuyển nhượng quyền sử dụng đất\n"
        "Vấn đề: Vấn đề tranh chấp hợp đồng chuyển nhượng quyền sử dụng đất\n\n"
        "Tên bản án: Yêu cầu xin ly hôn và phân chia tài sản\n"
        "Vấn đề: Vấn đề xin ly hôn và phân chia tài sản\n\n"
    )

    for i, case in enumerate(cases):
        print(f"[{i+1}/{len(cases)}] Processing: {case.uid}")

        # Ưu tiên title_parsed > title_web. Nếu không có cả hai -> Bỏ qua.
        input_title = case.title_parsed or case.title_web
        if not input_title:
            print(f"  -> Skipped: No title info")
            continue

        # GROUND TRUTH: gửi duy nhất title → rất ít token
        gt_prompt = (
            f"Dựa vào tên bản án, hãy viết lại thành một vấn đề pháp lý cốt lõi.\n"
            f"Yêu cầu:\n"
            f"- Bắt đầu bằng từ 'Vấn đề'\n"
            f"- Cực kỳ ngắn gọn (dưới 15 từ)\n"
            f"- Chỉ chứa chữ và số, không dùng dấu chấm, phẩy, ngoặc kép\n\n"
            f"{gt_examples}"
            f"Tên bản án: {input_title}\n"
            f"Vấn đề:"
        )

        raw_answer = llm.generate(gt_prompt)
        answer = raw_answer.strip().strip('"').strip("'").replace('.', '').replace(',', '')

        # Đảm bảo bắt đầu bằng "Vấn đề"
        if not answer.lower().startswith("vấn đề"):
            answer = "Vấn đề " + answer

        print(f"  -> Issue: {answer}")

        # CÂU HỎI: đầy đủ hướng dẫn + ví dụ format cho mô hình được đánh giá
        question = (
            f"Đọc tình huống pháp lý dưới đây và xác định vấn đề pháp lý cốt lõi.\n\n"
            f"Yêu cầu trả lời:\n"
            f"- Bắt đầu bằng từ 'Vấn đề'\n"
            f"- Ngắn gọn, súc tích (dưới 15 từ)\n"
            f"- Chỉ dùng chữ và số, không dùng dấu câu\n\n"
            f"{QUESTION_EXAMPLES}\n"
            f"Tình huống:\n{case.section_content}\n\n"
            f"Vấn đề pháp lý cốt lõi là gì?"
        )

        benchmark_data.append({
            "uid": f"bench_1_2_{case.uid}",
            "refer_uid": case.uid,
            "refer_type": "case",
            "question": question,
            "answer": answer
        })

    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_1_2.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 1.2 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    generate_task_1_2(limit=20)

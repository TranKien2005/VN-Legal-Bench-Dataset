import json
import random
import argparse
from pathlib import Path
from sqlalchemy.sql import func
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import CourtCase
from generator.llm_client import LLMClient

# Prompt tối ưu: Dùng Title và Decisions để sinh MCQ (Tiết kiệm token)
MCQ_PROMPT_TEMPLATE = """Dựa vào thông tin bản án dưới đây, hãy tạo câu hỏi trắc nghiệm về "Vấn đề pháp lý cốt lõi".

Tên bản án: {title}
Các quyết định của Tòa án:
{decisions}

Nhiệm vụ:
1. "correct": Trích xuất vấn đề pháp lý cốt lõi từ Tên bản án (Bắt đầu bằng 'Vấn đề...', ví dụ: 'Vấn đề tranh chấp hợp đồng đặt cọc').
2. "distractors": Sinh 3 vấn đề SAI. Yêu cầu:
   - Dựa vào nội dung 'Các quyết định' để tạo ra các vấn đề sai nhưng có vẻ liên quan (ví dụ: nếu tòa quyết định về bồi thường, hãy sinh vấn đề sai về 'Hủy hợp đồng').
   - Phải đảm bảo 3 vấn đề này SAI về bản chất so với Tên bản án gốc.
   - Không được quá lộ liễu, phải dùng thuật ngữ pháp lý tương đương.

Trả về duy nhất JSON:
{{
  "correct": "Vấn đề...",
  "distractors": ["Vấn đề...", "Vấn đề...", "Vấn đề..."]
}}"""

def generate_task_1_2(limit=50, use_all=False):
    """
    Task 1.2 — Core Issue Identification (MCQ Version - Optimized)
    Dùng Title + Decisions để sinh options, dùng Content để làm câu hỏi.
    """
    print(f"Starting Task 1.2 Generation (Use All: {use_all}, Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    # Lấy các bản án có đủ title, content và decisions
    query = session.query(CourtCase).filter(
        CourtCase.section_content != None,
        CourtCase.section_content != "",
        CourtCase.decision_items != None
    )

    if use_all:
        print("Mode: ALL — Processing all eligible cases sequentially")
        cases = query.order_by(CourtCase.uid.asc()).all()
    else:
        cases = query.order_by(func.random()).limit(limit).all()

    print(f"Found {len(cases)} candidate cases")
    benchmark_data = []

    for i, case in enumerate(cases):
        if not use_all and len(benchmark_data) >= limit:
            break
            
        print(f"[{i+1}/{'ALL' if use_all else len(cases)}] Processing: {case.uid}")

        input_title = case.title_parsed or case.title_web
        if not input_title or not case.section_content or not case.decision_items:
            print(f"  -> Skipped: Missing title, content, or decision_items")
            continue

        # Chuẩn bị thông tin bổ trợ để sinh distractors
        decisions_text = "\n".join([f"- {item}" for item in case.decision_items[:5]])

        # Gọi LLM sinh options (Rất ít token vì không gửi content)
        prompt = MCQ_PROMPT_TEMPLATE.format(title=input_title, decisions=decisions_text)
        raw_res = llm.generate(prompt)

        try:
            start = raw_res.find('{')
            end = raw_res.rfind('}') + 1
            res_json = json.loads(raw_res[start:end])
            correct = res_json.get("correct", "").strip()
            distractors = res_json.get("distractors", [])
        except Exception:
            print(f"  -> Skipped: Cannot parse LLM response")
            continue

        if not correct or len(distractors) < 3:
            continue

        # Trộn các phương án
        options = distractors[:3] + [correct]
        random.shuffle(options)

        # Cắt bỏ phần nhận định khỏi content để làm câu hỏi cho Benchmark
        from generator.task_3_1 import get_clean_case_content
        case_content = get_clean_case_content(case)

        question = (
            f"Đọc tình huống pháp lý dưới đây và chọn vấn đề pháp lý cốt lõi đúng nhất.\n\n"
            f"Tình huống:\n{case_content}\n\n"
            f"Vấn đề pháp lý cốt lõi là gì?"
        )

        benchmark_data.append({
            "uid": f"bench_1_2_{case.uid}",
            "refer_uid": case.uid,
            "refer_type": "case",
            "question": question,
            "options": options,
            "answer": correct
        })
        print(f"  -> OK: {correct[:50]}...")

    output_dir = Path("data/benchmark/issue_spotting")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_1_2.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 1.2 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh Benchmark cho Task 1.2")
    parser.add_argument("--limit", type=int, default=10, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Xử lý toàn bộ dữ liệu tuần tự")
    
    args = parser.parse_args()
    generate_task_1_2(limit=args.limit, use_all=args.all)

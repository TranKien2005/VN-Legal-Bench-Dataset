import json
from pathlib import Path
from sqlalchemy.sql import func
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import CourtCase
from config.constants import LEGAL_ISSUE_LABELS
from generator.llm_client import LLMClient

# 15 nhãn kèm mô tả được định dạng để LLM dễ nhận diện
LABELS_NUMBERED = "\n".join(
    f"{i+1}. {item['label']}: {item['description']}" 
    for i, item in enumerate(LEGAL_ISSUE_LABELS)
)

def _match_label_exact(answer: str) -> str:
    """
    Exact match trước, fallback fuzzy (substring) nếu không khớp.
    Trả về nhãn khớp hoặc nhãn mặc định.
    """
    answer_clean = answer.strip().strip('"').strip("'")
    # 1. Exact match
    for item in LEGAL_ISSUE_LABELS:
        label = item["label"]
        if label.lower() == answer_clean.lower():
            return label
    # 2. Fallback: LLM có thể trả về số thứ tự (ví dụ "1" hoặc "1. Hôn nhân và Gia đình")
    for i, item in enumerate(LEGAL_ISSUE_LABELS):
        label = item["label"]
        prefix = str(i + 1)
        if answer_clean.startswith(prefix + ".") or answer_clean == prefix:
            return label
    # 3. Fallback cuối: substring
    for item in LEGAL_ISSUE_LABELS:
        label = item["label"]
        if label.lower() in answer_clean.lower():
            return label
    return "Các vấn đề pháp lý khác"

import argparse

def generate_task_1_1(limit=50, use_all=False):
    """
    Task 1.1 — General Legal Issue Classification
    """
    print(f"Starting Task 1.1 Generation (Use All: {use_all}, Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    query = session.query(CourtCase).filter(
        CourtCase.section_content != None
    )

    if use_all:
        print("Mode: ALL — Processing all cases sequentially")
        cases = query.order_by(CourtCase.uid.asc()).all()
    else:
        cases = query.order_by(func.random()).limit(limit).all()

    print(f"Found {len(cases)} candidate cases")
    benchmark_data = []

    for i, case in enumerate(cases):
        if not use_all and len(benchmark_data) >= limit:
            break
            
        print(f"[{i+1}/{'ALL' if use_all else len(cases)}] Processing: {case.uid}")

        case_title = case.title_parsed or case.title_web
        if not case_title or not case.section_content:
            print(f"  -> Skipped: Missing title or content")
            continue
# ... (giữ nguyên phần logic tạo câu hỏi bên dưới)

        # GROUND TRUTH: gửi metadata ngắn gọn — tiết kiệm token
        metadata_context = (
            f"Tên bản án: {case_title}\n"
            f"Quan hệ pháp luật: {case.legal_relation}\n"
            f"Loại vụ án: {case.case_type}"
        )

        gt_prompt = (
            f"Dựa vào thông tin sau, xác định bản án thuộc nhãn nào trong danh sách.\n\n"
            f"Thông tin:\n{metadata_context}\n\n"
            f"Danh sách nhãn:\n{LABELS_NUMBERED}\n\n"
            f"Chỉ trả về đúng tên nhãn (không thêm gì khác)."
        )

        raw_answer = llm.generate(gt_prompt)
        final_answer = _match_label_exact(raw_answer)
        print(f"  -> Label: {final_answer}")

        # CÂU HỎI: đầy đủ nội dung + hướng dẫn rõ ràng
        question = (
            f"Đọc tình huống pháp lý dưới đây và xác định nó thuộc lĩnh vực pháp lý nào "
            f"trong danh sách 15 nhãn sau.\n\n"
            f"Danh sách nhãn:\n{LABELS_NUMBERED}\n\n"
            f"Tình huống:\n{case.section_content}\n\n"
            f"Yêu cầu: Chỉ trả về đúng tên nhãn phù hợp nhất (ví dụ: 'Hôn nhân và Gia đình')."
        )

        benchmark_data.append({
            "uid": f"bench_1_1_{case.uid}",
            "refer_uid": case.uid,
            "refer_type": "case",
            "question": question,
            "answer": final_answer
        })

    output_dir = Path("data/benchmark/issue_spotting")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_1_1.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 1.1 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh Benchmark cho Task 1.1")
    parser.add_argument("--limit", type=int, default=20, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Xử lý toàn bộ dữ liệu tuần tự")
    
    args = parser.parse_args()
    generate_task_1_1(limit=args.limit, use_all=args.all)

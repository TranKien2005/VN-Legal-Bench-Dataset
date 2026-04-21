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

def generate_task_1_1(limit=50):
    """
    Task 1.1 — General Legal Issue Classification
    Mục tiêu: Phân loại tình huống pháp lý vào 1 trong 15 nhãn.
    
    Ground truth: LLM đọc metadata bản án (title + legal_relation + case_type) → sinh nhãn.
    Câu hỏi: Cung cấp section_content + danh sách 15 nhãn → yêu cầu chọn nhãn.
    """
    print(f"Starting Task 1.1 Generation (Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    cases = session.query(CourtCase).filter(
        CourtCase.section_content != None
    ).order_by(func.random()).limit(limit).all()

    benchmark_data = []

    for i, case in enumerate(cases):
        print(f"[{i+1}/{len(cases)}] Processing: {case.uid}")

        # Ưu tiên title_parsed > title_web. Nếu không có cả hai -> Bỏ qua.
        case_title = case.title_parsed or case.title_web
        if not case_title:
            print(f"  -> Skipped: No title info")
            continue

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

    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_1_1.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 1.1 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    generate_task_1_1(limit=20)

import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.sql import func
from db.session import SessionLocal
from db.models import CourtCase, LegalDoc
from generator.llm_client import LLMClient
from generator.db_search_agent import find_doc_agentic, DB_SCHEMA_CONTEXT

# Prompt để LLM extract danh sách search params từ legal_bases
# (mỗi văn bản tham chiếu là một entry độc lập)
EXTRACT_LEGAL_BASES_PROMPT = """Đọc phần căn cứ pháp lý dưới đây trích từ một bản án.
Hãy xác định các văn bản pháp luật chính được tòa án áp dụng (bỏ qua nghị quyết về án phí).

Căn cứ pháp lý:
"{legal_bases}"

Trả về JSON danh sách (không thêm gì khác):
{{"docs": [
  {{"title_keywords": ["Hôn nhân", "Gia đình"], "doc_type": "Luật", "year": 2014}},
  {{"title_keywords": ["Tố tụng dân sự"], "doc_type": "Bộ luật", "year": 2015}}
]}}
(Tối đa 4 văn bản chính. title_keywords là mảng các từ khóa từ tên văn bản.)"""


def generate_task_2_6(limit=50):
    """
    Task 2.6 — Relevant Article Identification
    Mục tiêu: Xác định văn bản pháp luật liên quan đến một tình huống pháp lý.

    Flow:
    1. Lấy bản án có legal_bases
    2. LLM đọc legal_bases → extract list search params cho từng văn bản tham chiếu
    3. Agentic search từng văn bản → lấy được danh sách confirmed doc_uids
    4. MCQ: "Văn bản nào liên quan đến vụ án..." 
       - Input: legal_relation / core issue của vụ án
       - Correct: one confirmed doc
       - Distractors: 3 doc ngẫu nhiên KHÔNG có trong confirmed set
    """
    print(f"Starting Task 2.6 Generation (Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    # Lấy bản án có legal_bases
    cases = (
        session.query(CourtCase)
        .filter(CourtCase.legal_bases != None)
        .order_by(func.random())
        .limit(limit * 5)
        .all()
    )

    # Cache toàn bộ doc_id để lấy distractors
    all_docs = session.query(LegalDoc).filter(LegalDoc.doc_id != None).all()
    all_doc_by_uid = {d.uid: d for d in all_docs}

    benchmark_data = []

    for case in cases:
        if len(benchmark_data) >= limit:
            break

        print(f"[{len(benchmark_data)+1}/{limit}] Processing case: {case.uid}")

        legal_bases = case.legal_bases or ""
        if len(legal_bases) < 20:
            continue

        # ── Bước 1: LLM extract search params từ legal_bases ──
        prompt = EXTRACT_LEGAL_BASES_PROMPT.format(
            legal_bases=legal_bases[:2000]
        )
        raw = llm.generate(prompt)

        try:
            info = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
            doc_params_list = info.get("docs", [])
        except Exception:
            print(f"  -> Skipped: cannot parse LLM response")
            continue

        if not doc_params_list:
            continue

        # ── Bước 2: Agentic search từng văn bản ──
        confirmed_docs = []
        confirmed_uids = set()

        for params in doc_params_list[:4]:   # tối đa 4 văn bản
            hint = " ".join(params.get("title_keywords", []))
            result = find_doc_agentic(
                session, llm,
                content_hint=legal_bases[:800],
                context_instruction=(
                    f"Đang tìm văn bản: {hint} "
                    f"(type={params.get('doc_type')}, year={params.get('year')}). "
                    f"Tìm theo trường title trong legal_docs."
                )
            )
            if result and result["uid"] not in confirmed_uids:
                confirmed_docs.append(result)
                confirmed_uids.add(result["uid"])

        if not confirmed_docs:
            print(f"  -> Skipped: no confirmed docs found")
            continue

        # ── Bước 3: Tạo MCQ ──
        # Correct: chọn 1 trong confirmed docs, dùng doc_id làm đáp án
        correct_doc = random.choice(confirmed_docs)
        correct_answer = correct_doc["doc_id"]  # dùng doc_id tránh keyword matching

        # Distractors: doc_id ngẫu nhiên KHÔNG trong confirmed set
        distractor_pool = [
            d for d in all_docs
            if d.uid not in confirmed_uids
            and d.doc_id
            and d.doc_id != correct_answer
        ]
        if len(distractor_pool) < 3:
            continue

        distractors = [d.doc_id for d in random.sample(distractor_pool, 3)]
        options = distractors + [correct_answer]
        random.shuffle(options)

        # Câu hỏi dùng title (vấn đề của vụ án)
        van_de = case.title_parsed or case.title_web
        if not van_de:
            print(f"  -> Skipped: No title info")
            continue

        question = (
            f"Vấn đề pháp lý: '{van_de}'\n\n"
            f"Số hiệu văn bản pháp luật nào dưới đây liên quan trực tiếp nhất đến vấn đề nêu trên?\n\n"
            f"Chọn đáp án đúng (chỉ trả về số hiệu văn bản):"
        )

        benchmark_data.append({
            "uid": f"bench_2_6_{case.uid}",
            "refer_uid": case.uid,
            "refer_type": "case",
            "confirmed_doc_ids": [d["doc_id"] for d in confirmed_docs],
            "question": question,
            "options": options,
            "answer": correct_answer
        })

        print(f"  -> OK: {len(confirmed_docs)} docs confirmed, answer: {correct_answer}")

    # Lưu kết quả
    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_6.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.6 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    generate_task_2_6(limit=10)

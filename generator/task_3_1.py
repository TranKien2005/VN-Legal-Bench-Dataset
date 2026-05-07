import json
import random
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.sql import func
from db.session import SessionLocal
from db.models import CourtCase, LegalArticle, LegalDoc
from generator.llm_client import LLMClient
from generator.db_search_agent import find_doc_agentic, DB_SCHEMA_CONTEXT

# ─────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────

DECISION_PROMPT = """Đọc danh sách quyết định của tòa án dưới đây:

Căn cứ pháp lý áp dụng:
{legal_context}

Quyết định thực tế của Tòa án (Ground Truth):
{decision_text}

Nhiệm vụ:
1. Tạo đáp án ĐÚNG bằng cách trích xuất hoặc kết hợp các quyết định quan trọng nhất.

2. Sinh 3 đáp án SAI (Distractors) cực kỳ "HỢP LÝ" nhưng sai về luật:
   - SAI KHUNG HÌNH PHẠT: Dựa vào nội dung luật cung cấp, hãy sinh đáp án có mức hình phạt nằm ngoài khung (ví dụ: luật quy định 2-5 năm, đáp án sai đưa ra 7 năm).
   - SAI LOGIC ÁP DỤNG: Áp dụng sai các tình tiết tăng nặng/giảm nhẹ.
   - SAI ĐỐI TƯỢNG/TỶ LỆ: Thay đổi người chịu trách nhiệm hoặc tỷ lệ bồi thường nhưng giữ nguyên văn phong pháp lý.

Trả về duy nhất JSON:
{{"correct": "Nội dung quyết định ĐÚNG",
  "distractors": ["Đáp án SAI 1 (ngoài khung/sai luật)", 
                 "Đáp án SAI 2 (sai tình tiết/tỷ lệ)", 
                 "Đáp án SAI 3 (văn phong phức tạp tương đương)"]}}"""

LEGAL_BASES_EXTRACT_PROMPT = """Đọc phần căn cứ pháp lý dưới đây từ một bản án Việt Nam.
Xác định TẤT CẢ các văn bản pháp luật và điều khoản được trích dẫn.
Bỏ qua Nghị quyết về án phí (Nghị quyết 326/2016 hoặc 327/2021).

{schema}

Căn cứ pháp lý:
"{legal_bases}"

Trả về JSON danh sách (không thêm gì khác):
{{"refs": [
  {{
    "title_keywords": ["Hôn nhân", "Gia đình"],
    "doc_type": "Luật",
    "year": 2014,
    "article_numbers": ["33", "55", "56", "59"]
  }},
  {{
    "title_keywords": ["Tố tụng dân sự"],
    "doc_type": "Bộ luật",
    "year": 2015,
    "article_numbers": ["147", "227", "228", "244"]
  }}
]}}
(LƯU Ý: article_numbers chỉ chứa số/ký tự số, KHÔNG chứa chữ 'Điều'. Nếu không xác định được năm hoặc doc_type thì để null)"""


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def extract_refs_from_legal_bases(llm, legal_bases: str) -> list[dict]:
    prompt = LEGAL_BASES_EXTRACT_PROMPT.format(
        schema=DB_SCHEMA_CONTEXT,
        legal_bases=legal_bases[:2000]
    )
    raw = llm.generate(prompt)
    try:
        data = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
        return data.get("refs", [])
    except Exception:
        return []


def fetch_articles_from_refs(session, llm, refs: list[dict]) -> list[tuple]:
    found = []
    seen_ids = set()

    for ref in refs:
        title_keywords = ref.get("title_keywords", [])
        if not title_keywords:
            continue

        article_numbers = ref.get("article_numbers", [])
        if not article_numbers:
            continue

        hint = " ".join(title_keywords)
        context = (
            f"Đang tìm văn bản: {hint} "
            f"(type={ref.get('doc_type')}, year={ref.get('year')})"
        )
        doc_result = find_doc_agentic(
            session, llm,
            content_hint=hint,
            context_instruction=context
        )

        if not doc_result:
            continue

        doc = session.query(LegalDoc).filter(LegalDoc.uid == doc_result["uid"]).first()
        if not doc:
            continue

        for num in article_numbers[:10]:
            # Clean: remove 'Điều', 'điều' and whitespace
            clean_num = str(num).replace("Điều", "").replace("điều", "").strip()
            
            art = session.query(LegalArticle).filter(
                LegalArticle.doc_uid == doc.uid,
                func.lower(LegalArticle.article_number) == clean_num.lower()
            ).first()
            if art and art.article_id not in seen_ids:
                found.append((art, doc))
                seen_ids.add(art.article_id)

    return found


def format_legal_block(article_doc_pairs: list[tuple]) -> str:
    if not article_doc_pairs:
        return ""
    lines = ["[Các điều luật liên quan]"]
    for art, doc in article_doc_pairs:
        header = f"\nĐiều {art.article_number}"
        year = doc.issue_date.year if doc.issue_date else "không xác định"
        header += f" — {doc.title or doc.doc_id} ({year}):"
        lines.append(header)
        lines.append((art.content or "")[:1500])
    return "\n".join(lines)


_REASONING_MARKERS = [
    "NHẬN ĐỊNH CỦA TÒA",
    "NHẬN XÉT CỦA TÒA",
    "XÉT THẤY:",
    "Căn cứ vào tài liệu, chứng cứ đã được xem xét",
    "Hội đồng xét xử nhận định",
]


def get_clean_case_content(case) -> str:
    content = (case.section_content or "").strip()
    for marker in _REASONING_MARKERS:
        idx = content.find(marker)
        if idx > 200:
            content = content[:idx].strip()
            break
    return content


# ─────────────────────────────────────────────
# Generator chính
# ─────────────────────────────────────────────

def generate_task_3_1(limit=50, use_all=False):
    print(f"Starting Task 3.1 Generation (Use All: {use_all}, Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    query = session.query(CourtCase).filter(
        CourtCase.decision_items != None,
        CourtCase.section_content != None,
        CourtCase.section_content != "",
        CourtCase.legal_bases != None,
        CourtCase.legal_bases != "",
        CourtCase.court_level.ilike('%sơ thẩm%')
    )

    if use_all:
        print("Mode: ALL — Processing all eligible cases sequentially")
        candidates = query.order_by(CourtCase.uid.asc()).all()
    else:
        candidates = query.order_by(func.random()).limit(limit * 4).all()

    print(f"Found {len(candidates)} candidate first-trial cases")
    benchmark_data = []

    for case in candidates:
        if not use_all and len(benchmark_data) >= limit:
            break

        print(f"\n[{len(benchmark_data)+1}/{'ALL' if use_all else limit}] Processing: {case.uid}")

        # Kiểm tra điều kiện cần thiết cho Task 3.1
        if not case.section_content or not case.decision_items or not case.legal_bases:
            print(f"    -> Skipped: Missing core fields (content, decisions, or legal_bases)")
            continue

        items = case.decision_items
        if not isinstance(items, list) or len(items) < 2:
            continue

        refs = extract_refs_from_legal_bases(llm, case.legal_bases)
        if not refs:
            continue

        article_doc_pairs = fetch_articles_from_refs(session, llm, refs)
        total_expected = sum(len(ref.get("article_numbers", [])) for ref in refs)
        found_count = len(article_doc_pairs)

        if total_expected == 0 or found_count < total_expected:
            print(f"    -> Skipped: Found only {found_count}/{total_expected} articles.")
            continue

        legal_block = format_legal_block(article_doc_pairs)
        decision_text = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items[:10]))
        
        prompt = DECISION_PROMPT.format(
            decision_text=decision_text,
            legal_context=legal_block
        )
        raw = llm.generate(prompt)

        try:
            result = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
            correct = result.get("correct", "").strip()
            distractors = result.get("distractors", [])
        except Exception:
            continue

        if not correct or len(distractors) < 3:
            continue

        case_content = get_clean_case_content(case)
        if len(case_content) < 100:
            continue

        options = distractors[:3] + [correct]
        random.shuffle(options)

        question = (
            f"[Tình tiết vụ án]\n{case_content}\n\n"
            f"{legal_block}\n\n"
            f"Câu hỏi: Dựa trên tình tiết vụ án và các điều luật được cung cấp, "
            f"Tòa án đã đưa ra quyết định như thế nào?\n\n"
            f"Yêu cầu: Chỉ trả về nội dung đáp án đúng."
        )

        benchmark_data.append({
            "uid": f"bench_3_1_{case.uid}",
            "refer_uid": case.uid,
            "refer_type": "case",
            "num_articles_found": len(article_doc_pairs),
            "question": question,
            "options": options,
            "answer": correct,
            "explanation": case.section_reasoning
        })

    output_dir = Path("data/benchmark/rule_application")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_3_1.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"\nTask 3.1 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh Benchmark cho Task 3.1")
    parser.add_argument("--limit", type=int, default=10, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Xử lý toàn bộ dữ liệu tuần tự")
    
    args = parser.parse_args()
    generate_task_3_1(limit=args.limit, use_all=args.all)

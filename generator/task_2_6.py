import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.sql import func
from db.session import SessionLocal
from db.models import CourtCase, LegalDoc, LegalArticle
from generator.llm_client import LLMClient
from generator.db_search_agent import find_doc_agentic, DB_SCHEMA_CONTEXT

EXTRACT_LEGAL_BASES_PROMPT = """Đọc phần căn cứ pháp lý dưới đây trích từ một bản án.
Hãy xác định các văn bản pháp luật và điều khoản cụ thể được tòa án áp dụng.

Căn cứ pháp lý:
"{legal_bases}"

Trả về JSON danh sách (không thêm gì khác):
{{"docs": [
  {{
    "title_keywords": ["Hôn nhân", "Gia đình"], 
    "doc_type": "Luật", 
    "year": 2014,
    "article_number": "55"
  }},
  {{
    "title_keywords": ["Tố tụng dân sự"], 
    "doc_type": "Bộ luật", 
    "year": 2015,
    "article_number": "147"
  }}
]}}
(Tối đa 4 entry. article_number chỉ lấy SỐ, không chứa chữ 'Điều'.)"""


import argparse

def generate_task_2_6(limit=50, use_all=False):
    """
    Task 2.6 — Relevant Article Identification
    """
    print(f"Starting Task 2.6 Generation (Use All: {use_all}, Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    # Lấy bản án có legal_bases
    query = session.query(CourtCase).filter(CourtCase.legal_bases != None)

    if use_all:
        print("Mode: ALL — Processing all eligible cases sequentially")
        cases = query.order_by(CourtCase.uid.asc()).all()
    else:
        cases = query.order_by(func.random()).limit(limit * 5).all()

    # Cache toàn bộ doc_id để lấy distractors
    all_docs = session.query(LegalDoc).filter(LegalDoc.doc_id != None).all()
    all_doc_by_uid = {d.uid: d for d in all_docs}

    benchmark_data = []

    for i, case in enumerate(cases):
        if not use_all and len(benchmark_data) >= limit:
            break

        print(f"[{i+1}/{'ALL' if use_all else len(cases)}] Processing case: {case.uid}")

        legal_bases = case.legal_bases or ""
        van_de = case.title_parsed or case.title_web

        if len(legal_bases) < 20 or not van_de:
            print(f"  -> Skipped: Missing legal_bases or title info")
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

        # ── Bước 2: Agentic search từng văn bản và xác thực điều khoản ──
        confirmed_items = []  # Lưu list (article_obj, doc_obj)
        confirmed_uids = set()

        for params in doc_params_list[:4]:
            hint = " ".join(params.get("title_keywords", []))
            doc_result = find_doc_agentic(
                session, llm,
                content_hint=legal_bases[:800],
                context_instruction=(
                    f"Đang tìm văn bản: {hint} "
                    f"(type={params.get('doc_type')}, year={params.get('year')})."
                )
            )
            
            if doc_result:
                # Kiểm tra điều khoản có tồn tại không
                art_num = str(params.get("article_number", "")).replace("Điều", "").replace("điều", "").strip()
                if not art_num: continue

                article = session.query(LegalArticle).filter(
                    LegalArticle.doc_uid == doc_result["uid"],
                    func.lower(LegalArticle.article_number) == art_num.lower()
                ).first()

                if article and article.article_id not in confirmed_uids:
                    doc_obj = session.query(LegalDoc).filter(LegalDoc.uid == doc_result["uid"]).first()
                    confirmed_items.append((article, doc_obj))
                    confirmed_uids.add(article.article_id)

        if not confirmed_items:
            print(f"  -> Skipped: no confirmed articles found")
            continue

        # ── Bước 3: Tạo MCQ ──
        # Correct: chọn 1 trong confirmed articles
        correct_art, correct_doc = random.choice(confirmed_items)
        correct_answer = f"Điều {correct_art.article_number} {correct_doc.doc_id}"

        # Distractors: Lấy các điều khác trong cùng văn bản hoặc văn bản khác
        distractor_pool = []
        # Ưu tiên lấy các điều khác trong cùng văn bản đúng
        other_arts = session.query(LegalArticle).filter(
            LegalArticle.doc_uid == correct_doc.uid,
            LegalArticle.article_id != correct_art.article_id
        ).limit(10).all()
        
        for oa in other_arts:
            distractor_pool.append(f"Điều {oa.article_number} {correct_doc.doc_id}")

        if len(distractor_pool) < 3:
            # Nếu thiếu thì lấy từ văn bản ngẫu nhiên khác
            other_docs = random.sample(all_docs, min(5, len(all_docs)))
            for od in other_docs:
                if od.uid == correct_doc.uid: continue
                distractor_pool.append(f"Điều {random.randint(1, 100)} {od.doc_id}")

        distractors = random.sample(distractor_pool, 3)
        options = distractors + [correct_answer]
        random.shuffle(options)

        # Câu hỏi dùng title (vấn đề của vụ án)
        van_de = case.title_parsed or case.title_web
        if not van_de:
            print(f"  -> Skipped: No title info")
            continue

        question = (
            f"Vấn đề pháp lý: '{van_de}'\n\n"
            f"Điều khoản nào dưới đây liên quan trực tiếp nhất đến việc giải quyết vấn đề nêu trên?\n\n"
            f"Chọn đáp án đúng (chỉ trả về nội dung đáp án):"
        )

        benchmark_data.append({
            "uid": f"bench_2_6_{case.uid}",
            "refer_uid": case.uid,
            "refer_type": "case",
            "confirmed_article_ids": list(confirmed_uids),
            "question": question,
            "options": options,
            "answer": correct_answer
        })

        print(f"  -> OK: {len(confirmed_items)} articles confirmed, answer: {correct_answer}")

    # Lưu kết quả
    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_6.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.6 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh Benchmark cho Task 2.6")
    parser.add_argument("--limit", type=int, default=10, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Xử lý toàn bộ dữ liệu tuần tự")
    
    args = parser.parse_args()
    generate_task_2_6(limit=args.limit, use_all=args.all)

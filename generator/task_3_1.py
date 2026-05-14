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

DECISION_PROMPT = """Đọc toàn bộ căn cứ pháp lý liên quan và quyết định thực tế của Tòa án dưới đây.

Căn cứ pháp lý áp dụng:
{legal_context}

Quyết định thực tế của Tòa án (Ground Truth):
{decision_text}

Nhiệm vụ:
Hãy tạo 4 phương án trắc nghiệm (1 ĐÚNG, 3 SAI) về PHÁN QUYẾT TRỌNG TÂM của Tòa án.

YÊU CẦU VỀ ĐÁP ÁN ĐÚNG:
1. Chỉ chọn 1 kết luận trọng tâm nhất từ quyết định thực tế, không chép toàn bộ quyết định.
2. Ưu tiên các loại phán quyết chính: cho ly hôn hay không, giao con/cấp dưỡng; tội danh và mức hình phạt chính; chấp nhận/bác yêu cầu; số tiền bồi thường/nghĩa vụ thanh toán; tỉ lệ hoặc chủ thể được chia tài sản; hủy/sửa/giữ nguyên quyết định hành chính.
3. Bỏ qua án phí, quyền kháng cáo, hướng dẫn thi hành án, nghĩa vụ chậm thi hành án và các chi tiết thủ tục nếu không phải kết luận chính.
4. Viết như một trích đoạn phán quyết ngắn gọn, chuyên nghiệp, chỉ 1 câu hoặc 2 câu rất ngắn.

YÊU CẦU VỀ ĐÁP ÁN SAI:
1. Ba đáp án sai phải cùng loại phán quyết với đáp án đúng.
   - Nếu đáp án đúng là mức án tù, đáp án sai cũng là mức án tù khác, ưu tiên nằm trong hoặc gần khung hình phạt hợp lý theo điều luật.
   - Nếu đáp án đúng là chia tài sản/bồi thường/thanh toán, đáp án sai chỉ thay đổi số tiền, tỉ lệ, chủ thể hoặc nghĩa vụ chính.
   - Nếu đáp án đúng là chấp nhận/bác yêu cầu, đáp án sai đảo kết quả hoặc thay đổi một phần kết quả.
   - Nếu đáp án đúng là ly hôn/nuôi con/cấp dưỡng, đáp án sai thay đổi kết quả ly hôn, người trực tiếp nuôi con hoặc mức cấp dưỡng.
2. Không tạo đáp án sai phi lý, khác hẳn chủ đề, hoặc dựa vào án phí/quyền kháng cáo.
3. Tất cả 4 phương án phải có độ dài xấp xỉ nhau; không phương án nào dài vượt trội hoặc ngắn bất thường.
4. Các đáp án sai phải đánh lừa nhưng vẫn phù hợp với bối cảnh pháp lý và các điều luật liên quan.

Trả về duy nhất JSON:
{{"correct": "Phán quyết đúng trọng tâm, ngắn gọn",
  "distractors": [
    "Phán quyết sai 1 cùng loại và cùng độ dài",
    "Phán quyết sai 2 cùng loại và cùng độ dài",
    "Phán quyết sai 3 cùng loại và cùng độ dài"
  ]}}"""

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
    "doc_id": "52/2014/QH13",
    "article_numbers": ["33", "55", "56", "59"]
  }},
  {{
    "title_keywords": ["Tố tụng dân sự"],
    "doc_type": "Luật",
    "year": 2015,
    "doc_id": null,
    "article_numbers": ["147", "227", "228", "244"]
  }}
]}}
LƯU Ý: doc_type chỉ được là "Luật", "Bộ luật", "Nghị định", "Nghị quyết" hoặc "Hiến pháp". article_numbers chỉ chứa số/ký tự số, KHÔNG chứa chữ 'Điều'. Nếu không xác định được năm, doc_type hoặc doc_id thì để null."""


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def extract_refs_from_legal_bases(llm, legal_bases: str, debug: bool = False) -> list[dict]:
    prompt = LEGAL_BASES_EXTRACT_PROMPT.format(
        schema=DB_SCHEMA_CONTEXT,
        legal_bases=legal_bases[:2000]
    )
    raw = llm.generate(prompt)
    if debug:
        print("    [debug] legal_bases excerpt:", legal_bases[:500].replace("\n", " "))
        print("    [debug] refs raw:", raw[:1500])
    try:
        data = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
        refs = data.get("refs", [])
        if debug:
            print(f"    [debug] extracted refs: {json.dumps(refs, ensure_ascii=False)[:2000]}")
        return refs
    except Exception as e:
        if debug:
            print(f"    [debug] cannot parse refs JSON: {e}")
        return []


def fetch_articles_from_refs(session, llm, refs: list[dict], legal_bases: str, debug: bool = False) -> tuple[list[tuple], int]:
    found = []
    seen_ids = set()
    expected_resolvable = 0

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
        if debug:
            print(f"    [debug] ref: {json.dumps(ref, ensure_ascii=False)}")
        doc_result = find_doc_agentic(
            session, llm,
            content_hint=hint,
            context_instruction=context,
            title_keywords=title_keywords,
            doc_type=ref.get("doc_type"),
            year=ref.get("year"),
            doc_id=ref.get("doc_id"),
            article_numbers=article_numbers
        )

        if not doc_result:
            if debug:
                print("    [debug] doc_result: <none>")
            continue

        if debug:
            print(f"    [debug] selected doc: {json.dumps(doc_result, ensure_ascii=False)}")

        doc = session.query(LegalDoc).filter(LegalDoc.uid == doc_result["uid"]).first()
        if not doc:
            if debug:
                print(f"    [debug] selected uid missing in DB: {doc_result['uid']}")
            continue

        expected_resolvable += len(article_numbers)
        for num in article_numbers:
            # Clean: remove 'Điều', 'điều' and whitespace
            clean_num = str(num).replace("Điều", "").replace("điều", "").strip()

            art = session.query(LegalArticle).filter(
                LegalArticle.doc_uid == doc.uid,
                func.lower(LegalArticle.article_number) == clean_num.lower()
            ).first()
            if art and art.article_id not in seen_ids:
                found.append((art, doc))
                seen_ids.add(art.article_id)
                if debug:
                    print(f"    [debug] article found: Điều {clean_num} -> {art.article_id}")
            elif debug:
                print(f"    [debug] article missing: Điều {clean_num} in {doc.doc_id} | {doc.title}")

    return found, expected_resolvable


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

def generate_task_3_1(limit=50, use_all=False, debug=False):
    print(f"Starting Task 3.1 Generation (Use All: {use_all}, Limit: {limit}, Debug: {debug})...")
    session = SessionLocal()
    llm = LLMClient()

    query = session.query(CourtCase).filter(
        CourtCase.section_decision != None,
        CourtCase.section_content != None,
        CourtCase.section_content != "",
        CourtCase.legal_bases != None,
        CourtCase.legal_bases != "",
        CourtCase.court_level.ilike('%sơ thẩm%')
    )

    total_candidates = query.count()
    candidates = query.order_by(CourtCase.uid.asc()).yield_per(20)

    if use_all:
        print(f"Mode: ALL — Processing all {total_candidates} eligible cases sequentially")
    else:
        print(f"Mode: LIMIT — Processing sequentially until {limit} samples are generated")

    benchmark_data = []
    processed_cases = 0

    for case in candidates:
        if not use_all and len(benchmark_data) >= limit:
            break

        processed_cases += 1

        # Kiểm tra điều kiện cần thiết cho Task 3.1
        if not case.section_content or not case.section_decision or not case.legal_bases:
            if debug:
                print(f"\n[{len(benchmark_data)+1}/{'ALL' if use_all else limit}] Skip case {processed_cases}/{total_candidates}: {case.uid} — missing core fields")
            continue

        decision_text = (case.section_decision or "").strip()
        if len(decision_text) < 100:
            if debug:
                print(f"\n[{len(benchmark_data)+1}/{'ALL' if use_all else limit}] Skip case {processed_cases}/{total_candidates}: {case.uid} — decision text too short")
            continue

        print(f"\n[{len(benchmark_data)+1}/{'ALL' if use_all else limit}] Processing case {processed_cases}/{total_candidates}: {case.uid}")

        refs = extract_refs_from_legal_bases(llm, case.legal_bases, debug=debug)
        if not refs:
            if debug:
                print("    [debug] no refs extracted")
            continue

        article_doc_pairs, total_expected = fetch_articles_from_refs(session, llm, refs, case.legal_bases, debug=debug)
        found_count = len(article_doc_pairs)

        if total_expected == 0 or found_count < total_expected:
            print(f"    -> Skipped: Found only {found_count}/{total_expected} resolvable articles.")
            continue

        legal_block = format_legal_block(article_doc_pairs)

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
    parser.add_argument("--limit", type=int, default=5, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Xử lý toàn bộ dữ liệu tuần tự")
    parser.add_argument("--debug", action="store_true", help="In log chi tiết bước tìm văn bản/điều luật")

    args = parser.parse_args()
    generate_task_3_1(limit=args.limit, use_all=args.all, debug=args.debug)

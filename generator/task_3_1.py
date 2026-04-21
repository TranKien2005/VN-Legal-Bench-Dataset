import json
import random
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

{decision_text}

Nhiệm vụ:
1. Tạo đáp án ĐÚNG bằng cách trích xuất hoặc kết hợp các quyết định quan trọng nhất (hình phạt, bồi thường, tài sản, con cái).

2. Sinh 3 đáp án SAI (Distractors) mang tính "ĐÁNH LỪA" chuyên sâu, không máy móc:
   - ĐA DẠNG KỊCH BẢN PHÁP LÝ: Không được chỉ thay đổi con số hoặc số hiệu thửa đất. Hãy thay đổi bản chất logic của quyết định. (Ví dụ: Nếu đáp án đúng là 'Chia đôi tài sản', đáp án sai có thể là 'Tòa bác yêu cầu chia tài sản do là tài sản riêng' hoặc 'Chia theo tỷ lệ 1/3 - 2/3 do công sức đóng góp').
   - ĐẢO NGƯỢC KẾT QUẢ (CÂN BẰNG KHẲNG ĐỊNH/PHỦ ĐỊNH): Nếu đáp án đúng là Chấp nhận/Cho phép, ít nhất 1-2 đáp án sai phải là Bác/Không cho phép với các lý do pháp lý nghe rất thuyết phục.
   - BIẾN TẤU CẤU TRÚC CÂU: Mỗi lựa chọn nên có cách sắp xếp ý và hành văn khác nhau một chút nhưng vẫn giữ tông giọng trang trọng của Tòa án. Tránh việc 4 đáp án giống hệt nhau về cấu trúc chỉ khác mỗi con số.
   - CHI TIẾT TƯƠNG ĐƯƠNG: Nếu đáp án đúng có liệt kê số thửa đất, diện tích, số tiền lẻ... thì các đáp án sai CŨNG PHẢI liệt kê các thông tin chi tiết tương tự (có thể bịa ra các số liệu hợp lý khác) để đáp án đúng không bị nổi bật vì độ phức tạp.

Trả về duy nhất JSON:
{{"correct": "Nội dung quyết định ĐÚNG",
  "distractors": ["Đáp án SAI 1 (kịch bản khác, chi tiết, văn phong khác)", 
                 "Đáp án SAI 2 (đảo ngược kết quả hoặc thay đổi tỷ lệ/người hưởng)", 
                 "Đáp án SAI 3 (văn phong và chi tiết phức tạp y hệt đáp án đúng)"]}}"""

# Prompt để LLM extract danh sách văn bản + điều khoản từ legal_bases
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
(Nếu không xác định được năm hoặc doc_type thì để null)"""


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def extract_refs_from_legal_bases(llm, legal_bases: str) -> list[dict]:
    """LLM đọc legal_bases → trả về danh sách {title_keywords, doc_type, year, article_numbers}."""
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
    """
    Với mỗi ref: dùng find_doc_agentic để xác định doc_uid,
    rồi query articles theo article_numbers.
    Trả về list of (LegalArticle, LegalDoc).
    """
    found = []
    seen_ids = set()

    for ref in refs:
        title_keywords = ref.get("title_keywords", [])
        if not title_keywords:
            continue

        article_numbers = ref.get("article_numbers", [])
        if not article_numbers:
            continue

        # Dùng agentic search để tìm doc
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
            print(f"    [Article fetch] Cannot find doc: {hint}")
            continue

        doc = session.query(LegalDoc).filter(LegalDoc.uid == doc_result["uid"]).first()
        if not doc:
            continue

        print(f"    [Article fetch] Found doc: {doc.doc_id} | {doc.title[:50]}")

        # Query từng điều
        for num in article_numbers[:10]:
            art = session.query(LegalArticle).filter(
                LegalArticle.doc_uid == doc.uid,
                LegalArticle.article_number == num
            ).first()
            if art and art.article_id not in seen_ids:
                found.append((art, doc))
                seen_ids.add(art.article_id)

    return found


def format_legal_block(article_doc_pairs: list[tuple]) -> str:
    """Format danh sách điều luật thành block text nhúng vào câu hỏi."""
    if not article_doc_pairs:
        return ""
    lines = ["[Các điều luật liên quan]"]
    for art, doc in article_doc_pairs:
        header = f"\nĐiều {art.article_number}"
        # Lấy năm để làm rõ văn bản
        year = doc.issue_date.year if doc.issue_date else "không xác định"
        header += f" — {doc.title or doc.doc_id} ({year}):"
        lines.append(header)
        lines.append((art.content or "")[:1500])  # cap 1500 ký tự/điều
    return "\n".join(lines)


# Marker bắt đầu phần nhận định của tòa (cần cắt bỏ khỏi câu hỏi vì chứa gợi ý đáp án)
_REASONING_MARKERS = [
    "NHẬN ĐỊNH CỦA TÒA",
    "NHẬN XÉT CỦA TÒA",
    "XÉT THẤY:",
    "Căn cứ vào tài liệu, chứng cứ đã được xem xét",
    "Hội đồng xét xử nhận định",
]


def get_clean_case_content(case) -> str:
    """
    Lấy section_content và cắt bỏ phần nhận định nếu bị gộp vào.
    Phần nhận định (NHẬN ĐỊNH CỦA TÒA, Xét thấy,...) thường bắt đầu
    ngay sau phần tình tiết và chứa gợi ý về đáp án đúng.
    """
    content = (case.section_content or "").strip()
    for marker in _REASONING_MARKERS:
        idx = content.find(marker)
        # Chỉ cắt nếu có ít nhất 200 ký tự phần tình tiết trước đó
        if idx > 200:
            content = content[:idx].strip()
            break
    return content


# ─────────────────────────────────────────────
# Generator chính
# ─────────────────────────────────────────────

def generate_task_3_1(limit=50):
    """
    Task 3.1 — Legal Court Decision Prediction
    Mục tiêu: Dự đoán quyết định chính của tòa án dựa trên tình tiết + điều luật.

    Flow:
    1. Filter: bản án SƠ THẨM có decision_items + section_content + legal_bases
    2. LLM call 1: đọc decision_items → 1 quyết định chính + 3 distractors đa dạng
    3. LLM call 2: đọc legal_bases → extract danh sách {doc, article_numbers} cho từng văn bản
    4. find_doc_agentic cho từng văn bản → query article content từ DB
    5. Tự động ghép câu hỏi: section_content + article texts + MCQ
    """
    print(f"Starting Task 3.1 Generation (Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    # Lọc bản án sơ thẩm có đủ dữ liệu
    candidates = (
        session.query(CourtCase)
        .filter(
            CourtCase.decision_items != None,
            CourtCase.section_content != None,
            CourtCase.legal_bases != None,
            CourtCase.court_level.ilike('%sơ thẩm%')
        )
        .order_by(func.random())
        .limit(limit * 4)
        .all()
    )

    print(f"Found {len(candidates)} candidate first-trial cases")
    benchmark_data = []

    for case in candidates:
        if len(benchmark_data) >= limit:
            break

        print(f"\n[{len(benchmark_data)+1}/{limit}] Processing: {case.uid}")

        # Kiểm tra decision_items hợp lệ
        items = case.decision_items
        if not items or not isinstance(items, list) or len(items) < 2:
            print(f"  -> Skipped: insufficient decision_items")
            continue

        # ── Bước 1: LLM chọn decision + sinh distractors ──
        decision_text = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items[:10]))
        prompt = DECISION_PROMPT.format(decision_text=decision_text)
        raw = llm.generate(prompt)

        try:
            result = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
            correct = result.get("correct", "").strip()
            distractors = result.get("distractors", [])
        except Exception:
            print(f"  -> Skipped: cannot parse decision LLM response")
            continue

        if not correct or len(distractors) < 3:
            print(f"  -> Skipped: incomplete decision response")
            continue

        print(f"  -> Decision: {correct[:70]}")

        # ── Bước 2: LLM extract danh sách văn bản từ legal_bases ──
        refs = extract_refs_from_legal_bases(llm, case.legal_bases)
        print(f"  -> Extracted {len(refs)} doc refs from legal_bases")

        # ── Bước 3: Agentic search + query articles ──
        article_doc_pairs = fetch_articles_from_refs(session, llm, refs)
        legal_block = format_legal_block(article_doc_pairs)

        # Fallback: nếu không tìm được điều nào → dùng raw legal_bases
        if not legal_block:
            legal_block = f"[Căn cứ pháp lý]\n{case.legal_bases}"
            print(f"  -> Fallback: using raw legal_bases text")
        else:
            print(f"  -> Found {len(article_doc_pairs)} articles in DB")

        # ── Bước 4: Ghép câu hỏi tự động ──
        # Cắt bỏ phần nhận định khỏi section_content (chứa gợi ý đáp án)
        case_content = get_clean_case_content(case)
        if len(case_content) < 100:
            print(f"  -> Skipped: section_content too short after cleaning")
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
            "answer": correct
        })

        print(f"  -> OK")

    # Lưu kết quả
    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_3_1.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"\nTask 3.1 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    generate_task_3_1(limit=10)

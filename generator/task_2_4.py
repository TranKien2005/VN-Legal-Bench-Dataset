import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.sql import func
from db.session import SessionLocal
from db.models import LegalArticle, LegalDoc
from generator.llm_client import LLMClient
from generator.db_search_agent import find_doc_agentic, get_neighbor_articles
from generator.utils import get_stratified_articles

EXTRACT_PROMPT = """Đọc nội dung điều khoản sửa đổi bổ sung dưới đây.
Hãy xác định:
1. Điều khoản nào trong văn bản gốc đang bị sửa đổi (CHỈ TRẢ VỀ SỐ, ví dụ: 12, 33a)? 
   Nếu sửa nhiều điều, chỉ lấy điều đầu tiên trong danh sách.
2. Văn bản gốc là gì (tên và năm ban hành)?

Nội dung điều khoản sửa đổi:
"{content}"

Trả về JSON (không thêm gì khác):
{{"original_article_number": "12", "search_hint": "Luật Doanh nghiệp 2014", "title_keywords": ["Doanh nghiệp"], "doc_type": "Luật", "year": 2014}}
(year, doc_type có thể null nếu không rõ. original_article_number chỉ chứa số/ký tự số, KHÔNG chứa chữ 'Điều')"""


def generate_task_2_4(limit=50):
    """
    Task 2.4 — Legal Evolution
    Mục tiêu: Kiểm tra khả năng biết điều khoản nào sửa đổi điều khoản gốc.

    Flow:
    1. Lấy các điều sửa đổi (is_amendment=True)
    2. LLM extract: số điều gốc bị sửa + search params của văn bản gốc
    3. Agentic search → tìm doc_uid của văn bản gốc
    4. Xác nhận điều gốc tồn tại trong DB
    5. MCQ: "Điều X của [Văn bản gốc] bị sửa đổi bởi điều nào trong [Văn bản sửa đổi]?"
       - Correct: amendment article
       - Distractors: các điều lân cận trong cùng văn bản sửa đổi
    """
    print(f"Starting Task 2.4 Generation (Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    # Lấy mẫu các điều sửa đổi (ưu tiên is_amendment=True)
    amendment_articles = (
        session.query(LegalArticle)
        .filter(LegalArticle.is_amendment == True)
        .order_by(func.random())
        .limit(limit * 5)   # lấy dư để bù trừ những cái không tìm được doc gốc
        .all()
    )

    if not amendment_articles:
        print("Warning: No amendment articles found. Check is_amendment flag in DB.")
        session.close()
        return

    benchmark_data = []
    processed = 0

    for article in amendment_articles:
        if len(benchmark_data) >= limit:
            break

        processed += 1
        print(f"[{processed}] Processing amendment: {article.article_id}")

        # Lấy thông tin văn bản sửa đổi (amendment doc)
        amend_doc = session.query(LegalDoc).filter(LegalDoc.uid == article.doc_uid).first()
        if not amend_doc:
            continue

        # ── Bước 1: LLM extract info từ nội dung điều sửa đổi ──
        prompt = EXTRACT_PROMPT.format(content=article.content[:2000])
        raw = llm.generate(prompt)

        try:
            info = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
        except Exception:
            print(f"  -> Skipped: cannot parse LLM response")
            continue

        if not info or not info.get("original_article_number"):
            print(f"  -> Skipped: no original article found")
            continue

        original_article_number = str(info["original_article_number"]).strip()
        # Clean: remove 'Điều', 'điều' and take the first one if it's a list
        original_article_number = original_article_number.replace("Điều", "").replace("điều", "").strip()
        if "," in original_article_number:
            original_article_number = original_article_number.split(",")[0].strip()
        
        search_hint = info.get("search_hint", "")

        # ── Bước 2: Agentic search tìm văn bản gốc ──
        context_instruction = (
            f"Đang tìm văn bản gốc mà điều này sửa đổi. "
            f"Gợi ý: {search_hint}"
        )
        original_doc = find_doc_agentic(
            session, llm,
            content_hint=article.content[:1200],
            context_instruction=context_instruction
        )

        if not original_doc:
            print(f"  -> Skipped: cannot find original doc")
            continue

        # Đảm bảo không phải cùng văn bản với amendment
        if original_doc["uid"] == amend_doc.uid:
            print(f"  -> Skipped: found same doc as amendment")
            continue

        # ── Bước 3: Kiểm tra điều gốc tồn tại trong DB ──
        original_article = (
            session.query(LegalArticle)
            .filter(
                LegalArticle.doc_uid == original_doc["uid"],
                func.lower(LegalArticle.article_number) == original_article_number.lower()
            )
            .first()
        )

        if not original_article:
            print(f"  -> Skipped: Article {original_article_number} not found in {original_doc['doc_id']}")
            continue

        # ── Bước 4: Tạo MCQ ──
        # Correct answer: amendment article (cái chúng ta đang xét)
        correct_answer = f"Điều {article.article_number} của {amend_doc.doc_id}"

        # Distractors: các điều lân cận trong cùng amendment doc
        neighbor_arts = get_neighbor_articles(
            session, amend_doc.uid, article.article_id, count=3
        )
        if len(neighbor_arts) < 3:
            print(f"  -> Skipped: not enough neighbor articles for distractors")
            continue

        distractors = [f"Điều {a.article_number} của {amend_doc.doc_id}" for a in neighbor_arts]
        options = distractors + [correct_answer]
        random.shuffle(options)

        # Lấy đầy đủ tiêu đề kèm năm
        original_doc_year = original_doc.get("year") or "không xác định"
        original_full_title = f"{original_doc['title']} ({original_doc_year})"
        
        amend_doc_year = amend_doc.issue_date.year if amend_doc.issue_date else "không xác định"
        amend_full_title = f"{amend_doc.title} ({amend_doc_year})"

        question = (
            f"Điều {original_article_number} của '{original_full_title}' "
            f"đã được sửa đổi, bổ sung bởi điều khoản nào trong '{amend_full_title}'?\n\n"
            f"Chọn đáp án đúng (chỉ trả về nội dung đáp án):"
        )

        benchmark_data.append({
            "uid": f"bench_2_4_{article.article_id}",
            "refer_uid": article.article_id,
            "refer_type": "article",
            "original_article_id": original_article.article_id,
            "question": question,
            "options": options,
            "answer": correct_answer
        })

        print(f"  -> OK: Q about Điều {original_article_number} of {original_doc['doc_id']}, "
              f"A: Điều {article.article_number} of {amend_doc.doc_id}")

    # Lưu kết quả
    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_4.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.4 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    generate_task_2_4(limit=50)

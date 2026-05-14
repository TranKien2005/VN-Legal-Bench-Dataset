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

EXTRACT_PROMPT = """Đọc nội dung điều khoản sửa đổi bổ sung dưới đây.
Hãy xác định:
1. Điều khoản nào trong văn bản gốc đang bị sửa đổi (CHỈ TRẢ VỀ SỐ, ví dụ: 12, 33a)?
   Nếu sửa nhiều điều, chỉ lấy điều đầu tiên trong danh sách.
2. Văn bản gốc là gì (tên, năm ban hành và số hiệu nếu có)?

Nội dung điều khoản sửa đổi:
"{content}"

Trả về JSON (không thêm gì khác):
{{"original_article_number": "12", "search_hint": "Luật Doanh nghiệp 2014", "title_keywords": ["Doanh nghiệp"], "doc_type": "Luật", "year": 2014, "doc_id": "68/2014/QH13"}}
doc_type chỉ được là "Luật", "Bộ luật", "Nghị định", "Nghị quyết" hoặc "Hiến pháp". year, doc_type, doc_id có thể null nếu không rõ. original_article_number chỉ chứa số/ký tự số, KHÔNG chứa chữ 'Điều'."""

NOT_AMENDED_OPTION = "Điều này chưa được sửa đổi, bổ sung trong dữ liệu hiện có"


def _clean_article_number(value) -> str:
    text = str(value or "").replace("Điều", "").replace("điều", "").strip()
    if "," in text:
        text = text.split(",")[0].strip()
    return text


def _answer_label(article: LegalArticle, doc: LegalDoc) -> str:
    return f"Điều {article.article_number} của {doc.doc_id}"


def generate_task_2_4(limit=50):
    """
    Task 2.4 — Legal Evolution
    Hỏi từ phía điều gốc: điều gốc được sửa đổi, bổ sung bởi điều khoản nào sau đây.
    """
    print(f"Starting Task 2.4 Generation (Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    amendment_articles = (
        session.query(LegalArticle)
        .filter(LegalArticle.is_amendment == True)
        .order_by(func.random())
        .limit(limit * 8)
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

        amend_doc = session.query(LegalDoc).filter(LegalDoc.uid == article.doc_uid).first()
        if not amend_doc:
            print("  -> Skipped: amendment doc not found in DB")
            continue

        print(f"  amendment doc: {amend_doc.doc_id} | {amend_doc.title} | year={amend_doc.issue_date.year if amend_doc.issue_date else 'unknown'}")

        raw = llm.generate(EXTRACT_PROMPT.format(content=article.content[:2000]))
        try:
            info = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
        except Exception:
            print(f"  -> Skipped: cannot parse LLM response: {raw[:300]}")
            continue

        print(
            "  extracted original: "
            f"article={info.get('original_article_number')} | "
            f"hint={info.get('search_hint')} | "
            f"keywords={info.get('title_keywords')} | "
            f"type={info.get('doc_type')} | "
            f"year={info.get('year')} | "
            f"doc_id={info.get('doc_id')}"
        )

        original_article_number = _clean_article_number(info.get("original_article_number"))
        if not original_article_number:
            print("  -> Skipped: LLM did not identify an original article number")
            continue

        search_hint = info.get("search_hint", "")
        original_doc = find_doc_agentic(
            session, llm,
            content_hint=article.content[:1200],
            context_instruction=f"Đang tìm văn bản gốc mà điều này sửa đổi. Gợi ý: {search_hint}",
            title_keywords=info.get("title_keywords"),
            doc_type=info.get("doc_type"),
            year=info.get("year"),
            doc_id=info.get("doc_id"),
            article_numbers=[original_article_number]
        )

        if not original_doc:
            print(
                "  -> Skipped: cannot find original doc from extracted params "
                f"for article {original_article_number}"
            )
            continue

        print(
            "  selected original doc: "
            f"{original_doc.get('doc_id')} | {original_doc.get('title')} | "
            f"year={original_doc.get('year')} | uid={original_doc.get('uid')} | "
            f"score={original_doc.get('score')} | reasons={original_doc.get('reasons')}"
        )

        if original_doc["uid"] == amend_doc.uid:
            print(
                "  -> Skipped: search selected the amendment doc itself, "
                "so no separate original doc was resolved"
            )
            continue

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

        correct_answer = _answer_label(article, amend_doc)
        neighbor_arts = get_neighbor_articles(session, amend_doc.uid, article.article_id, count=4)
        distractors = [_answer_label(a, amend_doc) for a in neighbor_arts if a.article_id != article.article_id]
        distractors.append(NOT_AMENDED_OPTION)
        distractors = list(dict.fromkeys(d for d in distractors if d != correct_answer))

        if len(distractors) < 3:
            print("  -> Skipped: not enough distractors")
            continue

        options = random.sample(distractors, 3) + [correct_answer]
        random.shuffle(options)

        original_doc_year = original_doc.get("year") or "không xác định"
        original_full_title = f"{original_doc['title']} ({original_doc_year})"

        question = (
            f"Điều {original_article_number} của '{original_full_title}' "
            f"được sửa đổi, bổ sung bởi điều khoản nào sau đây?\n\n"
            f"Chọn đáp án đúng (chỉ trả về nội dung đáp án):"
        )

        benchmark_data.append({
            "uid": f"bench_2_4_{original_article.article_id}_{article.article_id}",
            "refer_uid": original_article.article_id,
            "refer_type": "article",
            "amendment_article_id": article.article_id,
            "question": question,
            "options": options,
            "answer": correct_answer
        })

        print(f"  -> OK: Điều {original_article_number} of {original_doc['doc_id']} amended by {correct_answer}")

    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_4.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.4 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    generate_task_2_4(limit=100)

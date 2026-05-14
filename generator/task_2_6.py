import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.sql import func
from db.session import SessionLocal
from db.models import LegalDoc, LegalArticle
from generator.utils import is_core_article


def _article_label(article: LegalArticle, doc: LegalDoc) -> str:
    return f"Điều {article.article_number} {doc.doc_id}"


def _clean_field(field: str | None) -> str | None:
    if not field:
        return None
    text = str(field).strip()
    if not text or text.lower() in {"đang cập nhật", "không xác định", "none"}:
        return None
    return text


def generate_task_2_6(limit=50, use_all=False):
    """
    Task 2.6 — Relevant Article Identification by Legal Field.
    Chọn điều khoản liên quan đến một chủ đề pháp lý, chỉ hiển thị id điều khoản/văn bản.
    """
    print(f"Starting Task 2.6 Generation by legal_field (Use All: {use_all}, Limit: {limit})...")
    session = SessionLocal()

    rows = (
        session.query(LegalArticle, LegalDoc)
        .join(LegalDoc, LegalArticle.doc_uid == LegalDoc.uid)
        .filter(LegalDoc.legal_field != None)
        .filter(LegalDoc.legal_field != "")
        .filter(LegalDoc.doc_id != None)
        .filter(LegalArticle.article_number != None)
        .all()
    )

    by_field = defaultdict(list)
    for article, doc in rows:
        field = _clean_field(doc.legal_field)
        if field and is_core_article(session, article):
            by_field[field].append((article, doc))

    eligible_fields = [field for field, items in by_field.items() if len(items) >= 1]
    if len(eligible_fields) < 4:
        print("Warning: not enough legal_field groups for distractors.")
        session.close()
        return

    benchmark_data = []
    attempts = 0
    max_attempts = len(rows) if use_all else limit * 20

    while (use_all or len(benchmark_data) < limit) and attempts < max_attempts:
        attempts += 1
        correct_field = random.choice(eligible_fields)
        correct_article, correct_doc = random.choice(by_field[correct_field])
        correct_answer = _article_label(correct_article, correct_doc)

        other_fields = [field for field in eligible_fields if field != correct_field]
        random.shuffle(other_fields)
        distractors = []
        used_answers = {correct_answer}

        for field in other_fields:
            if len(distractors) >= 3:
                break
            article, doc = random.choice(by_field[field])
            label = _article_label(article, doc)
            if label not in used_answers:
                distractors.append(label)
                used_answers.add(label)

        if len(distractors) < 3:
            continue

        options = distractors + [correct_answer]
        random.shuffle(options)

        benchmark_data.append({
            "uid": f"bench_2_6_{correct_article.article_id}",
            "refer_uid": correct_article.article_id,
            "refer_type": "article",
            "legal_field": correct_field,
            "question": (
                f"Điều khoản nào dưới đây liên quan trực tiếp nhất đến chủ đề pháp lý: '{correct_field}'?\n\n"
                f"Chọn đáp án đúng (chỉ trả về nội dung đáp án):"
            ),
            "options": options,
            "answer": correct_answer
        })

        print(f"  -> OK: {correct_field} | answer: {correct_answer}")

        if use_all and attempts >= len(rows):
            break

    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_6.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.6 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh Benchmark cho Task 2.6")
    parser.add_argument("--limit", type=int, default=100, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Sinh nhiều mẫu dựa trên dữ liệu hiện có")

    args = parser.parse_args()
    generate_task_2_6(limit=args.limit)
                    #   , use_all=args.all)

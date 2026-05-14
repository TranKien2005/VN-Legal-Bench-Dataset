import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import LegalArticle, LegalDoc
from generator.utils import get_stratified_articles


def _get_short_excerpt(content: str, max_sentences: int = 2) -> str:
    if not content:
        return ""
    sentences = [s.strip() for s in content.replace('\n', ' ').split('.') if s.strip()]
    excerpt = '. '.join(sentences[:max_sentences])
    if excerpt and not excerpt.endswith('.'):
        excerpt += '.'
    return excerpt


def _article_label(article: LegalArticle, doc: LegalDoc) -> str:
    return f"Điều {article.article_number} {doc.doc_id}"


def generate_task_2_3(limit=50):
    """
    Task 2.3 — Legal Metadata Identification
    1. Excerpt -> doc_id
    2. Excerpt -> article number + doc_id
    3. doc_id -> effective_date
    4. doc_id -> signer
    """
    print(f"Starting Task 2.3 Generation (Exact Metadata Recall, Limit: {limit})...")
    session = SessionLocal()

    articles = get_stratified_articles(session, max(limit, 20))
    all_docs = session.query(LegalDoc).filter(LegalDoc.doc_id != None).all()
    doc_map = {d.uid: d for d in all_docs}

    benchmark_data = []

    random.shuffle(articles)
    for article in articles:
        if len(benchmark_data) >= limit // 2:
            break

        doc = doc_map.get(article.doc_uid)
        if not doc or not doc.doc_id or not article.article_number:
            continue

        excerpt = _get_short_excerpt(article.content)
        if not excerpt:
            continue

        if random.random() < 0.5:
            benchmark_data.append({
                "uid": f"bench_2_3_docid_{article.article_id}",
                "refer_uid": article.article_id,
                "refer_type": "article",
                "question": (
                    f"Đoạn trích dưới đây thuộc văn bản pháp luật có số hiệu nào?\n\n"
                    f"\"{excerpt}\"\n\n"
                    f"Yêu cầu: Chỉ trả về số hiệu văn bản."
                ),
                "answer": doc.doc_id
            })
        else:
            benchmark_data.append({
                "uid": f"bench_2_3_article_{article.article_id}",
                "refer_uid": article.article_id,
                "refer_type": "article",
                "question": (
                    f"Đoạn trích dưới đây thuộc điều khoản nào của văn bản pháp luật nào?\n\n"
                    f"\"{excerpt}\"\n\n"
                    f"Yêu cầu: Trả về theo mẫu 'Điều [số điều] [số hiệu văn bản]'."
                ),
                "answer": _article_label(article, doc)
            })

    docs_with_effective_date = [d for d in all_docs if d.effective_date]
    docs_with_signer = [d for d in all_docs if d.signer]

    metadata_target = max(0, limit - len(benchmark_data))
    date_target = metadata_target // 2
    signer_target = metadata_target - date_target

    for doc in random.sample(docs_with_effective_date, min(len(docs_with_effective_date), date_target)):
        benchmark_data.append({
            "uid": f"bench_2_3_effective_{doc.uid}",
            "refer_uid": doc.uid,
            "refer_type": "doc",
            "question": (
                f"Văn bản pháp luật có số hiệu '{doc.doc_id}' có hiệu lực từ ngày nào?\n\n"
                f"Yêu cầu: Trả về ngày theo định dạng DD/MM/YYYY."
            ),
            "answer": doc.effective_date.strftime("%d/%m/%Y")
        })

    for doc in random.sample(docs_with_signer, min(len(docs_with_signer), signer_target)):
        benchmark_data.append({
            "uid": f"bench_2_3_signer_{doc.uid}",
            "refer_uid": doc.uid,
            "refer_type": "doc",
            "question": (
                f"Ai là người ký văn bản pháp luật có số hiệu '{doc.doc_id}'?\n\n"
                f"Yêu cầu: Chỉ trả về tên người ký."
            ),
            "answer": doc.signer
        })

    benchmark_data = benchmark_data[:limit]
    random.shuffle(benchmark_data)

    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_3.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.3 Complete. {len(benchmark_data)} samples saved to {output_file}")


if __name__ == "__main__":
    generate_task_2_3(limit=100)

import json
import random
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import LegalArticle, LegalDoc
from generator.utils import get_stratified_articles, normalize_legal_text

# Hướng dẫn trả lời cố định nhúng vào câu hỏi
ANSWER_INSTRUCTION = (
    "Yêu cầu trả lời: Chỉ trả về nội dung của điều đó dưới dạng văn xuôi liên tục. "
    "Loại bỏ tất cả ký hiệu xuống dòng, số thứ tự đầu mục (1., 2., a., b., -) và dấu câu đặc biệt. "
    "Chỉ giữ lại chữ, số và khoảng trắng."
)

import argparse

def generate_task_2_2(limit=50, use_all=False):
    """
    Task 2.2 — Article Recall
    Mục tiêu: Kiểm tra khả năng ghi nhớ chính xác nội dung điều luật.
    """
    print(f"Starting Task 2.2 Generation (Use All: {use_all}, Limit: {limit})...")
    session = SessionLocal()

    articles_to_process = []
    
    if use_all:
        print("Mode: ALL — Processing all documents with custom rules (>=10 arts -> 5, <10 arts -> 1)")
        docs = session.query(LegalDoc).all()
        for doc in docs:
            # Lấy toàn bộ điều của văn bản này
            doc_articles = session.query(LegalArticle).filter(LegalArticle.doc_uid == doc.uid).order_by(LegalArticle.article_number).all()
            if not doc_articles:
                continue
            
            # Quy tắc: >= 10 điều lấy 5 ngẫu nhiên, < 10 điều lấy 1 ngẫu nhiên
            num_to_take = 5 if len(doc_articles) >= 10 else 1
            selected = random.sample(doc_articles, num_to_take)
            articles_to_process.extend(selected)
    else:
        # Lấy mẫu phân bổ stratified (logic cũ)
        articles_to_process = get_stratified_articles(session, limit)

    benchmark_data = []

    for i, article in enumerate(articles_to_process):
        if not use_all and i >= limit:
            break
            
        print(f"[{i+1}/{len(articles_to_process)}] Processing: {article.article_id}")

        # Lấy thông tin văn bản
        doc = session.query(LegalDoc).filter(LegalDoc.uid == article.doc_uid).first()
        if not doc:
            continue

        doc_title = doc.title or doc.doc_id or "văn bản pháp luật"
        answer = normalize_legal_text(article.content)
        if not answer:
            continue

        issue_year = doc.issue_date.year if doc.issue_date else "không xác định"

        question = (
            f"Nêu nguyên văn nội dung Điều {article.article_number} của {doc_title} (ban hành năm {issue_year}).\n\n"
            f"{ANSWER_INSTRUCTION}"
        )

        benchmark_data.append({
            "uid": f"bench_2_2_{article.article_id}",
            "refer_uid": article.article_id,
            "refer_doc_id": doc.doc_id,
            "refer_type": "article",
            "question": question,
            "answer": answer
        })

    # Lưu kết quả
    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_2.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.2 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sinh Benchmark cho Task 2.2")
    parser.add_argument("--limit", type=int, default=10, help="Số lượng mẫu tối đa (nếu không dùng --all)")
    parser.add_argument("--all", action="store_true", help="Xử lý toàn bộ dữ liệu theo quy tắc đặc thù")
    
    args = parser.parse_args()
    generate_task_2_2(limit=args.limit, use_all=args.all)

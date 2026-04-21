import json
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

def generate_task_2_2(limit=50):
    """
    Task 2.2 — Article Recall
    Mục tiêu: Kiểm tra khả năng ghi nhớ chính xác nội dung điều luật.
    Sinh hoàn toàn tự động từ DB, không cần LLM.
    Input: Tên điều + tên văn bản.
    Output: Nội dung điều đã normalize (chỉ chữ và số, bỏ hết format).
    """
    print(f"Starting Task 2.2 Generation (Fully Automatic, Limit: {limit})...")
    session = SessionLocal()

    # Lấy mẫu phân bổ stratified (80% Luật, 18% Nghị định, 2% Special)
    articles = get_stratified_articles(session, limit)

    benchmark_data = []

    for i, article in enumerate(articles):
        print(f"[{i+1}/{len(articles)}] Processing: {article.article_id}")

        # Lấy thông tin văn bản
        doc = session.query(LegalDoc).filter(LegalDoc.uid == article.doc_uid).first()
        if not doc:
            print(f"  -> Skipped: no doc found for uid={article.doc_uid}")
            continue

        doc_title = doc.title or doc.doc_id or "văn bản pháp luật"

        # Normalize đáp án: bỏ xuống dòng, dấu câu, số thứ tự
        answer = normalize_legal_text(article.content)
        if not answer:
            print(f"  -> Skipped: empty content after normalization")
            continue

        # Lấy năm ban hành để thông tin đầy đủ hơn
        issue_year = doc.issue_date.year if doc.issue_date else "không xác định"

        # Câu hỏi không chứa nội dung điều — chỉ tên điều, tên văn bản và năm
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
    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_2.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.2 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    generate_task_2_2(limit=10)

import json
import random
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import LegalArticle, LegalDoc
from sqlalchemy.sql import func
from generator.utils import get_stratified_articles

def _get_short_excerpt(content: str, max_sentences: int = 2) -> str:
    """Lấy đoạn trích ngắn để làm câu hỏi."""
    if not content:
        return ""
    sentences = [s.strip() for s in content.replace('\n', ' ').split('.') if s.strip()]
    excerpt = '. '.join(sentences[:max_sentences])
    if excerpt and not excerpt.endswith('.'):
        excerpt += '.'
    return excerpt

def generate_task_2_3(limit=50):
    """
    Task 2.3 — Legal Metadata Identification (Exact Match Version)
    1. Excerpt -> doc_id
    2. doc_id -> issue_date
    3. doc_id -> status (Only "Còn hiệu lực" / "Hết hiệu lực")
    """
    print(f"Starting Task 2.3 Generation (Exact Match, Limit: {limit})...")
    session = SessionLocal()

    # Lấy mẫu bài viết để làm Dạng 1
    articles = get_stratified_articles(session, limit // 2)
    
    # Lấy mẫu văn bản để làm Dạng 2 và 3
    all_docs = session.query(LegalDoc).filter(LegalDoc.doc_id != None).all()
    
    benchmark_data = []

    # --- DẠNG 1: Đoạn trích -> Số hiệu ---
    doc_map = {d.uid: d for d in all_docs}
    for article in articles:
        doc = doc_map.get(article.doc_uid)
        if not doc or not doc.doc_id:
            continue
            
        excerpt = _get_short_excerpt(article.content)
        if not excerpt:
            continue

        benchmark_data.append({
            "uid": f"bench_2_3_id_{article.article_id}",
            "refer_uid": article.article_id,
            "refer_type": "article",
            "question": (
                f"Đoạn trích dưới đây thuộc văn bản pháp luật có số hiệu nào?\n\n"
                f"\"{excerpt}\"\n\n"
                f"Yêu cầu: Chỉ trả về số hiệu văn bản. (Ví dụ trả lời: 03/2022/QH15)"
            ),
            "answer": doc.doc_id
        })

    # --- DẠNG 2: Số hiệu -> Ngày ban hành ---
    # Lọc lấy các doc có ngày ban hành
    docs_with_date = [d for d in all_docs if d.issue_date]
    sample_2 = random.sample(docs_with_date, min(len(docs_with_date), limit // 4))
    
    for doc in sample_2:
        # Chuyển định dạng ngày sang DD/MM/YYYY cho phổ thông
        date_str = doc.issue_date.strftime("%d/%m/%Y")
        
        benchmark_data.append({
            "uid": f"bench_2_3_date_{doc.uid}",
            "refer_uid": doc.uid,
            "refer_type": "doc",
            "question": (
                f"Văn bản pháp luật có số hiệu '{doc.doc_id}' được ban hành vào ngày tháng năm nào?\n\n"
                f"Yêu cầu: Trả về ngày theo định dạng DD/MM/YYYY. (Ví dụ trả lời: 11/01/2022)"
            ),
            "answer": date_str
        })

    # --- DẠNG 3: Số hiệu -> Trạng thái ---
    # Chỉ lấy "Còn hiệu lực" hoặc "Hết hiệu lực"
    valid_statuses = ["Còn hiệu lực", "Hết hiệu lực"]
    docs_with_status = [d for d in all_docs if d.status in valid_statuses]
    sample_3 = random.sample(docs_with_status, min(len(docs_with_status), limit // 4))
    
    for doc in sample_3:
        benchmark_data.append({
            "uid": f"bench_2_3_status_{doc.uid}",
            "refer_uid": doc.uid,
            "refer_type": "doc",
            "question": (
                f"Tình trạng hiệu lực hiện tại của văn bản có số hiệu '{doc.doc_id}' là gì?\n\n"
                f"Yêu cầu: Chỉ trả về tình trạng hiệu lực. (Ví dụ trả lời: Còn hiệu lực)"
            ),
            "answer": doc.status
        })

    # Lưu kết quả
    output_dir = Path("data/benchmark/rule_recall")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_3.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.3 Complete. {len(benchmark_data)} samples saved to {output_file}")

if __name__ == "__main__":
    generate_task_2_3(limit=50)

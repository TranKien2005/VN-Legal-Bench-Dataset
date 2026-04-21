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

def _get_short_excerpt(content: str, max_sentences: int = 3) -> str:
    """Lấy tối đa max_sentences câu đầu của nội dung điều khoản."""
    if not content:
        return ""
    # Split theo dấu chấm, lấy max_sentences câu
    sentences = [s.strip() for s in content.replace('\n', ' ').split('.') if s.strip()]
    excerpt = '. '.join(sentences[:max_sentences])
    if excerpt and not excerpt.endswith('.'):
        excerpt += '.'
    return excerpt

def _get_distractors(session, correct_value: str, field: str, doc_type: str = None, count: int = 3) -> list:
    """Lấy distractors cùng loại với đáp án đúng."""
    query = session.query(LegalDoc)
    if doc_type:
        query = query.filter(LegalDoc.doc_type == doc_type)
    
    all_docs = query.all()
    pool = []
    
    for d in all_docs:
        val = getattr(d, field, None)
        if val:
            if field == "title":
                # Bổ sung năm vào tiêu đề cho nhất quán
                year = d.issue_date.year if d.issue_date else "không xác định"
                val = f"{val} ({year})"
            
            if str(val) != str(correct_value):
                pool.append(str(val))
    
    # Deduplicate
    pool = list(set(pool))
    
    if len(pool) < count:
        return pool
    return random.sample(pool, count)

def generate_task_2_3(limit=50):
    """
    Task 2.3 — Legal Text Attribution
    Mục tiêu: Xác định thông tin nguồn gốc/metadata của văn bản luật.
    Sinh hoàn toàn tự động từ DB, không cần LLM.
    
    Type A: Đoạn trích ngắn (3 câu) → Tên văn bản (MCQ)
    Type B: Tên văn bản → Metadata (cơ quan ban hành / ngày / lĩnh vực) (MCQ)
    """
    print(f"Starting Task 2.3 Generation (Fully Automatic, Limit: {limit})...")
    session = SessionLocal()

    # Lấy mẫu phân bổ
    articles = get_stratified_articles(session, limit)
    
    # Cache tất cả docs
    all_docs = session.query(LegalDoc).all()
    doc_by_uid = {d.uid: d for d in all_docs}

    benchmark_data = []
    
    # Phân bổ 50/50 Type A và B
    target_a = limit // 2
    target_b = limit - target_a
    count_a, count_b = 0, 0

    for i, article in enumerate(articles):
        doc = doc_by_uid.get(article.doc_uid)
        if not doc or not doc.title:
            continue

        # Xác định loại câu hỏi theo target còn lại
        if count_a < target_a and (count_b >= target_b or random.random() > 0.5):
            # === TYPE A: Đoạn trích → Tên văn bản ===
            excerpt = _get_short_excerpt(article.content, max_sentences=3)
            if not excerpt:
                continue

            # Tên văn bản kèm năm
            issue_year = doc.issue_date.year if doc.issue_date else "không xác định"
            correct_answer = f"{doc.title} ({issue_year})"
            
            distractors = _get_distractors(
                session, correct_answer, "title", doc_type=doc.doc_type, count=3
            )
            if len(distractors) < 3:
                continue

            options = distractors + [correct_answer]
            random.shuffle(options)

            benchmark_data.append({
                "uid": f"bench_2_3_A_{article.article_id}",
                "refer_uid": article.article_id,
                "refer_type": "article",
                "question_type": "A",
                "question": (
                    f"Đoạn văn bản dưới đây được trích từ văn bản quy phạm pháp luật nào?\n\n"
                    f"\"{excerpt}\"\n\n"
                    f"Chọn đáp án đúng từ các lựa chọn sau (chỉ trả về tên văn bản):"
                ),
                "options": options,
                "answer": correct_answer
            })
            count_a += 1

        elif count_b < target_b:
            # === TYPE B: Tên văn bản → Metadata ===
            # Random 1 trong 3 loại câu hỏi metadata
            b_types = []
            if doc.issuing_body:
                b_types.append("issuing_body")
            if doc.issue_date:
                b_types.append("issue_date")
            if doc.doc_type:
                b_types.append("doc_type")
            
            if not b_types:
                continue
            
            chosen = random.choice(b_types)
            
            # Tên văn bản kèm năm cho Type B
            issue_year = doc.issue_date.year if doc.issue_date else "không xác định"
            full_doc_title = f"{doc.title} ({issue_year})"
            
            if chosen == "issuing_body":
                q_suffix = f"Cơ quan nào có thẩm quyền ban hành '{full_doc_title}'?"
                correct_answer = doc.issuing_body
                question_type = "B1"
            elif chosen == "issue_date":
                q_suffix = f"'{full_doc_title}' được ban hành vào ngày nào?"
                correct_answer = str(doc.issue_date)
                question_type = "B2"
            else:  # doc_type
                q_suffix = f"'{full_doc_title}' là loại văn bản pháp luật nào?"
                correct_answer = doc.doc_type
                question_type = "B3"
            
            distractors = _get_distractors(
                session, correct_answer, chosen, count=3
            )
            if len(distractors) < 3:
                continue

            options = distractors + [correct_answer]
            random.shuffle(options)

            benchmark_data.append({
                "uid": f"bench_2_3_{question_type}_{doc.uid}",
                "refer_uid": doc.uid,
                "refer_type": "doc",
                "question_type": question_type,
                "question": q_suffix + "\n\nChọn đáp án đúng (chỉ trả về đáp án):",
                "options": options,
                "answer": correct_answer
            })
            count_b += 1

        if count_a >= target_a and count_b >= target_b:
            break

    # Lưu kết quả
    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_3.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.3 Complete. {len(benchmark_data)} samples (A:{count_a}, B:{count_b}) saved to {output_file}")

if __name__ == "__main__":
    generate_task_2_3(limit=10)

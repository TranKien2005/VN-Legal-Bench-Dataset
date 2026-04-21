import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import LegalArticle, LegalDoc
from sqlalchemy.sql import func
from generator.llm_client import LLMClient

# Phân bổ tỷ lệ loại văn bản
DOC_TYPE_RATIOS = {
    "Luật": 0.80,
    "Nghị định": 0.18,
    "special": 0.02,   # HP2013
}
SPECIAL_DOC_ID = "HP2013"

# Prompt kiểm tra khái niệm (gửi đúng 1 điều tại một lần — tiết kiệm token)
SYSTEM_PROMPT = (
    "Bạn là chuyên gia pháp lý Việt Nam, có khả năng xác định và trích xuất định nghĩa "
    "khái niệm từ văn bản luật."
)

EXTRACT_PROMPT_TEMPLATE = (
    "Đọc nội dung điều khoản sau và xác định xem nó có chứa định nghĩa chính thức "
    "cho một khái niệm pháp lý không.\n\n"
    "Điều {article_number}. {article_title}\n"
    "Văn bản: {doc_title} (năm {issue_year})\n"
    "Nội dung:\n"
    "\"{content}\"\n\n"
    "Nếu điều khoản này có định nghĩa: trả về JSON dạng:\n"
    "{{\"co\": \"co\", \"ten_khai_niem\": \"<tên khái niệm>\", \"giai_thich\": \"<trích nguyên văn định nghĩa>\"}}\n"
    "Nếu không có định nghĩa: trả về JSON:\n"
    "{{\"co\": \"khong\"}}\n"
    "Chỉ trả về JSON, không thêm bất kỳ nội dung nào khác."
)

def _fetch_batch(session, doc_type: str, batch_size: int, exclude_ids: set) -> list:
    """Lấy batch điều khoản theo doc_type, bỏ qua những id đã xử lý."""
    if doc_type == "special":
        query = session.query(LegalArticle).join(LegalDoc).filter(
            LegalDoc.doc_id == SPECIAL_DOC_ID,
            ~LegalArticle.article_id.in_(exclude_ids)
        )
    else:
        query = session.query(LegalArticle).join(LegalDoc).filter(
            LegalDoc.doc_type == doc_type,
            ~LegalArticle.article_id.in_(exclude_ids)
        )
    return query.order_by(func.random()).limit(batch_size).all()

def generate_task_2_1(limit=50):
    """
    Task 2.1 — Definition Recall
    Mục tiêu: Kiểm tra khả năng nhớ định nghĩa khái niệm pháp lý trong một văn bản nhất định.
    
    Strategy:
    - Loop-until-full: fetch từng batch theo tỷ lệ stratified,
      gửi LLM kiểm tra từng điều (chỉ đọc nội dung 1 điều/lần),
      append nếu có khái niệm, tiếp tục đến khi đủ limit.
    - Câu hỏi KHÔNG chứa nội dung điều — chỉ hỏi tên khái niệm trong văn bản.
    """
    print(f"Starting Task 2.1 Generation (Loop-Until-Full, Limit: {limit})...")
    session = SessionLocal()
    llm = LLMClient()

    # Tính target mỗi loại
    targets = {
        "Luật": int(limit * DOC_TYPE_RATIOS["Luật"]),
        "Nghị định": int(limit * DOC_TYPE_RATIOS["Nghị định"]),
        "special": limit - int(limit * DOC_TYPE_RATIOS["Luật"]) - int(limit * DOC_TYPE_RATIOS["Nghị định"]),
    }
    print(f"Targets: {targets}")

    counts = {"Luật": 0, "Nghị định": 0, "special": 0}
    exclude_ids = set()   # track đã xử lý để tránh trùng
    benchmark_data = []
    BATCH_SIZE = 10       # mỗi lần fetch 10 điều, tránh query quá lớn

    max_iterations = limit * 10  # safety limit tránh vòng lặp vô tận
    iteration = 0

    while sum(counts.values()) < limit and iteration < max_iterations:
        iteration += 1

        # Lấy loại văn bản còn thiếu
        remaining_types = [t for t, c in counts.items() if c < targets[t]]
        if not remaining_types:
            break

        for doc_type in remaining_types:
            need = targets[doc_type] - counts[doc_type]
            if need <= 0:
                continue

            batch = _fetch_batch(session, doc_type, min(BATCH_SIZE, need * 3), exclude_ids)
            if not batch:
                print(f"  -> No more articles available for type: {doc_type}")
                # Đánh dấu type này đã hết để tránh lặp vô tận
                targets[doc_type] = counts[doc_type]
                continue

            for article in batch:
                exclude_ids.add(article.article_id)

                if counts[doc_type] >= targets[doc_type]:
                    break

                # Lấy doc info
                doc = session.query(LegalDoc).filter(LegalDoc.uid == article.doc_uid).first()
                if not doc or not article.content:
                    continue

                doc_title = doc.title or doc.doc_id or "văn bản pháp luật"

                # Lấy năm ban hành
                issue_year = doc.issue_date.year if doc.issue_date else "không xác định"

                # Gửi LLM — kèm theo cả tiêu đề Điều để nhận diện khái niệm tốt hơn
                prompt = EXTRACT_PROMPT_TEMPLATE.format(
                    article_number=article.article_number,
                    article_title=article.title or "",
                    doc_title=doc_title,
                    issue_year=issue_year,
                    content=article.content[:2000]  # cap 2000 ký tự để tránh quá dài
                )

                response = llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

                try:
                    start = response.find('{')
                    end = response.rfind('}') + 1
                    res_json = json.loads(response[start:end])
                except Exception:
                    res_json = {"co": "khong"}

                if res_json.get("co") == "co":
                    concept = res_json.get("ten_khai_niem", "").strip()
                    definition = res_json.get("giai_thich", "").strip()

                    if not concept or not definition:
                        continue

                    # Câu hỏi không chứa nội dung điều
                    question = (
                        f"Trong {doc_title} (ban hành năm {issue_year}), khái niệm '{concept}' được định nghĩa như thế nào?\n\n"
                        f"Yêu cầu: Chỉ trả lời bằng nội dung định nghĩa, "
                        f"trích nguyên văn từ luật, không thêm lời giải thích hay mở đầu."
                    )

                    benchmark_data.append({
                        "uid": f"bench_2_1_{article.article_id}",
                        "refer_uid": article.article_id,
                        "refer_doc_id": doc.doc_id,
                        "refer_type": "article",
                        "concept": concept,
                        "question": question,
                        "answer": definition
                    })
                    counts[doc_type] += 1
                    print(f"  [{doc_type}] Found: '{concept}' in {article.article_id} — total: {sum(counts.values())}/{limit}")

    # Lưu kết quả
    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "task_2_1.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    session.close()
    print(f"Task 2.1 Complete. {len(benchmark_data)} samples saved to {output_file}")
    print(f"Final counts: {counts}")

if __name__ == "__main__":
    generate_task_2_1(limit=20)

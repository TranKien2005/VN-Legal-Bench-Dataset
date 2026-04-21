"""
DB Search Agent (Hướng 2)
--------------------------
Cho phép LLM tìm doc_uid trong database theo vòng lặp:
  1. LLM extract search params từ nội dung
  2. Code query DB → trả về danh sách candidates  
  3. Nếu candidates ≤ CONFIRM_THRESHOLD → gửi cho LLM chọn
  4. Nếu vẫn nhiều và còn rounds → LLM tinh chỉnh params
  5. Tối đa MAX_ROUNDS vòng
"""

import json
from sqlalchemy import extract as sql_extract
from db.models import LegalDoc, LegalArticle

MAX_ROUNDS = 3
CONFIRM_THRESHOLD = 10   # Khi ≤ N kết quả → gửi cho LLM confirm luôn

# Mô tả schema gửi kèm mỗi prompt để LLM biết cách truy vấn
DB_SCHEMA_CONTEXT = """
[Database Schema — Văn bản pháp luật]
Bảng legal_docs:
  - uid      (TEXT, PK): khóa chính duy nhất, KHÔNG tự đoán được, phải truy vấn
  - doc_id   (TEXT): số hiệu, ví dụ "59/2020/QH14", "44/2005/QH11"
  - title    (TEXT): tên VIẾT HOA, ví dụ "LUẬT DOANH NGHIỆP", "BỘ LUẬT DÂN SỰ"
  - doc_type (TEXT): "Luật" | "Nghị định" | "Thông tư" | "Nghị quyết" | "Pháp lệnh"...
  - issuing_body (TEXT): "Quốc hội" | "Chính phủ" | "Bộ Tư pháp"...
  - issue_date (DATE): ngày ban hành

Bảng legal_articles:
  - article_id (TEXT, PK): dạng "dieu-{số}-{doc_uid}"
  - article_number (TEXT): số điều, ví dụ "12", "33a"
  - doc_uid (FK → legal_docs.uid)
"""


# ─────────────────────────────────────────────
# Hàm truy vấn DB
# ─────────────────────────────────────────────

def query_docs(session, title_keywords=None, doc_type=None, year=None, limit=50):
    """Truy vấn legal_docs theo keyword / type / year. Trả về list LegalDoc."""
    q = session.query(LegalDoc)
    if title_keywords:
        for kw in title_keywords:
            kw = kw.strip()
            if kw:
                q = q.filter(LegalDoc.title.ilike(f'%{kw}%'))
    if doc_type:
        q = q.filter(LegalDoc.doc_type == doc_type)
    if year:
        try:
            q = q.filter(sql_extract('year', LegalDoc.issue_date) == int(year))
        except Exception:
            pass
    return q.limit(limit).all()


def format_candidates(docs):
    """Format danh sách docs ngắn gọn để LLM dễ đọc và chọn."""
    lines = []
    for d in docs:
        year = d.issue_date.year if d.issue_date else "?"
        lines.append(
            f"  uid={d.uid} | doc_id={d.doc_id} | "
            f"title={d.title} | type={d.doc_type} | year={year}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Hàm agentic chính
# ─────────────────────────────────────────────

def find_doc_agentic(session, llm, content_hint: str, context_instruction: str = "") -> dict | None:
    """
    Tìm doc phù hợp qua vòng lặp LLM ↔ DB.

    Params:
        content_hint: đoạn text ngắn mà LLM dựa vào để tìm doc (max ~1500 ký tự)
        context_instruction: hướng dẫn thêm cho LLM biết đang tìm cái gì

    Returns:
        {"uid": ..., "doc_id": ..., "title": ...} hoặc None nếu thất bại
    """
    # ── Round 0: Extract params ──────────────────
    extract_prompt = (
        f"{DB_SCHEMA_CONTEXT}\n\n"
        f"Nhiệm vụ: Dựa vào đoạn văn bản dưới đây, xác định văn bản pháp luật được đề cập "
        f"và trả về JSON tham số tìm kiếm.\n"
        f"{context_instruction}\n\n"
        f"Nội dung:\n\"{content_hint[:1500]}\"\n\n"
        f"Trả về JSON (không thêm gì khác):\n"
        f"{{\"title_keywords\": [\"từ khóa 1\", \"từ khóa 2\"], "
        f"\"doc_type\": \"Luật\", \"year\": 2020}}\n"
        f"(Để null nếu không rõ year hoặc doc_type)"
    )

    raw = llm.generate(extract_prompt)
    try:
        params = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
    except Exception:
        return None

    docs = []
    # ── Vòng lặp tìm kiếm ───────────────────────
    for round_n in range(MAX_ROUNDS):
        docs = query_docs(
            session,
            title_keywords=params.get("title_keywords"),
            doc_type=params.get("doc_type"),
            year=params.get("year"),
            limit=50
        )

        if not docs:
            break  # Không tìm thấy gì

        if len(docs) == 1:
            d = docs[0]
            return {"uid": d.uid, "doc_id": d.doc_id, "title": d.title}

        if len(docs) <= CONFIRM_THRESHOLD:
            # Đủ nhỏ để gửi cho LLM chọn
            confirm_prompt = (
                f"Từ nội dung: \"{content_hint[:600]}\"\n\n"
                f"Chọn văn bản pháp luật phù hợp nhất từ danh sách (chỉ trả về uid):\n"
                f"{format_candidates(docs)}\n\n"
                f"uid của văn bản đúng là:"
            )
            chosen_uid = llm.generate(confirm_prompt).strip().strip('"').strip("'").split()[0]
            matched = next((d for d in docs if d.uid == chosen_uid), None)
            if matched:
                return {"uid": matched.uid, "doc_id": matched.doc_id, "title": matched.title}
            # LLM chọn sai → fallback first result
            d = docs[0]
            return {"uid": d.uid, "doc_id": d.doc_id, "title": d.title}

        # Còn nhiều + còn rounds: tinh chỉnh
        if round_n < MAX_ROUNDS - 1:
            refine_prompt = (
                f"Tìm kiếm trả về {len(docs)} kết quả (quá nhiều). "
                f"Nội dung cần tìm: \"{content_hint[:500]}\"\n"
                f"Params hiện tại: {json.dumps(params, ensure_ascii=False)}\n\n"
                f"Thêm keyword hoặc điều kiện để thu hẹp xuống còn dưới {CONFIRM_THRESHOLD}. "
                f"Trả về JSON mới:\n"
                f"{{\"title_keywords\": [...], \"doc_type\": \"...\", \"year\": ...}}"
            )
            raw2 = llm.generate(refine_prompt)
            try:
                params = json.loads(raw2[raw2.find('{'):raw2.rfind('}') + 1])
            except Exception:
                break

    # Hết rounds nhưng vẫn có docs → lấy first
    if docs:
        d = docs[0]
        return {"uid": d.uid, "doc_id": d.doc_id, "title": d.title}
    return None


def get_neighbor_articles(session, doc_uid: str, exclude_article_id: str, count: int = 3) -> list:
    """Lấy các điều lân cận trong cùng văn bản làm distractors."""
    all_arts = (
        session.query(LegalArticle)
        .filter(LegalArticle.doc_uid == doc_uid)
        .filter(LegalArticle.article_id != exclude_article_id)
        .limit(count + 5)
        .all()
    )
    import random
    pool = [a for a in all_arts if a.article_id != exclude_article_id]
    random.shuffle(pool)
    return pool[:count]

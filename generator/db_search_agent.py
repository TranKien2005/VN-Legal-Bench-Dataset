"""
DB Search Agent cho legal_docs/legal_articles.

Luồng chính:
  1. Caller truyền search params đã extract được nếu có.
  2. Code query rộng và rank candidates theo doc_id/title/type/year.
  3. Gửi top candidates cho LLM chọn uid hoặc null.
  4. Không fallback chọn candidate đầu tiên khi không chắc.
"""

import json
import re
from sqlalchemy import or_
from db.models import LegalDoc, LegalArticle

TOP_CANDIDATES_FOR_LLM = 5

DB_SCHEMA_CONTEXT = """
[Database Schema — Văn bản pháp luật]
Bảng legal_docs:
  - uid      (TEXT, PK): khóa chính duy nhất, KHÔNG tự đoán được, phải truy vấn
  - doc_id   (TEXT): số hiệu, ví dụ "59/2020/QH14", "44/2005/QH11"
  - title    (TEXT): tên văn bản, ví dụ "LUẬT DOANH NGHIỆP", "BỘ LUẬT DÂN SỰ"
  - doc_type (TEXT): chỉ dùng 1 trong 5 loại "Luật" | "Bộ luật" | "Nghị định" | "Nghị quyết" | "Hiến pháp".
  - issuing_body (TEXT): "Quốc hội" | "Chính phủ"...
  - issue_date (DATE): ngày ban hành

Bảng legal_articles:
  - article_id (TEXT, PK): dạng "dieu-{số}-{doc_uid}"
  - article_number (TEXT): số điều, ví dụ "12", "33a"
  - doc_uid (FK → legal_docs.uid)
"""

_DOC_ID_PATTERN = re.compile(r"\b\d{1,4}/\d{4}/[A-ZĐ0-9/-]+\b", re.IGNORECASE)
_ALLOWED_DOC_TYPES = {"luật": "Luật", "bộ luật": "Bộ luật", "nghị định": "Nghị định", "nghị quyết": "Nghị quyết", "hiến pháp": "Hiến pháp"}
_DOC_TYPE_ALIASES = {
    "bộ luật": "Bộ luật",
    "luật sửa đổi": "Luật",
    "luật": "Luật",
    "nghị định": "Nghị định",
    "nghị quyết": "Nghị quyết",
    "hiến pháp": "Hiến pháp",
}


def normalize_doc_type(doc_type: str | None) -> str | None:
    if not doc_type:
        return None
    text = str(doc_type).strip().lower()
    for key, value in _DOC_TYPE_ALIASES.items():
        if key in text:
            return value
    return _ALLOWED_DOC_TYPES.get(text)


def normalize_doc_id(doc_id: str | None) -> str | None:
    if not doc_id:
        return None
    text = str(doc_id).upper().strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace("Đ", "D")
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def extract_doc_ids(*texts: str | None) -> list[str]:
    found = []
    seen = set()
    for text in texts:
        if not text:
            continue
        for match in _DOC_ID_PATTERN.findall(text):
            normalized = normalize_doc_id(match)
            if normalized and normalized not in seen:
                found.append(normalized)
                seen.add(normalized)
    return found


def clean_keywords(title_keywords=None) -> list[str]:
    if not title_keywords:
        return []
    stop_words = {"luật", "bộ luật", "nghị định", "nghị quyết", "hiến pháp", "năm"}
    cleaned = []
    seen = set()
    for kw in title_keywords:
        text = str(kw).strip()
        if len(text) <= 1 or text.lower() in stop_words:
            continue
        lowered = text.lower()
        if lowered not in seen:
            cleaned.append(text)
            seen.add(lowered)
    return cleaned


def safe_year(year) -> int | None:
    if not year:
        return None
    try:
        value = int(year)
    except (TypeError, ValueError):
        return None
    if 1800 <= value <= 2100:
        return value
    return None


def doc_to_result(doc: LegalDoc, score: int | None = None, reasons: list[str] | None = None) -> dict:
    result = {
        "uid": doc.uid,
        "doc_id": doc.doc_id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "year": doc.issue_date.year if doc.issue_date else None,
    }
    if score is not None:
        result["score"] = score
    if reasons is not None:
        result["reasons"] = reasons
    return result


def _doc_id_like_patterns(normalized_doc_id: str) -> list[str]:
    if not normalized_doc_id:
        return []
    patterns = [normalized_doc_id]
    m = re.match(r"^(\d+)(\d{4})([A-Z0-9]+)$", normalized_doc_id)
    if m:
        number, year, suffix = m.groups()
        patterns.append(f"{number}/{year}")
        patterns.append(f"{number}/{year}/{suffix}")
        if suffix.startswith("NDCP"):
            patterns.append(f"{number}/{year}/NĐ-CP")
            patterns.append(f"{number}/{year}/ND-CP")
        if suffix.startswith("QH"):
            patterns.append(f"{number}/{year}/QH")
    return list(dict.fromkeys(patterns))


def _candidate_query(session, keywords, doc_type, year, doc_ids, content_hint, hard_limit):
    if doc_ids:
        doc_clauses = []
        for doc_id in doc_ids:
            for pattern in _doc_id_like_patterns(doc_id):
                doc_clauses.append(LegalDoc.doc_id.ilike(f"%{pattern}%"))
        docs = session.query(LegalDoc).filter(or_(*doc_clauses)).limit(hard_limit).all()
        if docs:
            return docs

    clauses = []
    for kw in keywords:
        clauses.append(LegalDoc.title.ilike(f"%{kw}%"))
        clauses.append(LegalDoc.doc_id.ilike(f"%{kw}%"))
    if doc_type:
        clauses.append(LegalDoc.doc_type == doc_type)
    if year:
        clauses.append(LegalDoc.doc_id.ilike(f"%{year}%"))

    query = session.query(LegalDoc)
    if clauses:
        query = query.filter(or_(*clauses))

    return query.order_by(LegalDoc.issue_date.desc().nullslast(), LegalDoc.uid.asc()).limit(hard_limit).all()


def _score_doc(doc, keywords, doc_type, year, doc_ids):
    score = 0
    reasons = []
    title = (doc.title or "").lower()
    db_doc_id = normalize_doc_id(doc.doc_id) or ""
    db_doc_type = normalize_doc_type(doc.doc_type)
    db_year = doc.issue_date.year if doc.issue_date else None

    for doc_id in doc_ids:
        if doc_id and doc_id == db_doc_id:
            score += 120
            reasons.append(f"doc_id exact: {doc_id}")
        elif doc_id and (doc_id in db_doc_id or db_doc_id in doc_id):
            score += 90
            reasons.append(f"doc_id partial: {doc_id}")

    if year and db_year == year:
        score += 40
        reasons.append(f"year match: {year}")
    elif year and str(year) in db_doc_id:
        score += 15
        reasons.append(f"year appears in doc_id: {year}")
    elif year and db_year and db_year != year:
        score -= 20
        reasons.append(f"year differs: {db_year}")

    compatible_type = doc_type == "Bộ luật" and db_doc_type == "Luật" and "bộ luật" in title
    if doc_type and (db_doc_type == doc_type or compatible_type):
        score += 30
        reasons.append(f"doc_type match: {doc_type}")
    elif doc_type and db_doc_type and db_doc_type != doc_type:
        score -= 35
        reasons.append(f"doc_type differs: {db_doc_type}")

    for kw in keywords:
        lowered = kw.lower()
        if lowered in title:
            score += 15
            reasons.append(f"title keyword: {kw}")
        elif lowered in db_doc_id.lower():
            score += 8
            reasons.append(f"doc_id keyword: {kw}")

    if not reasons:
        score -= 10
        reasons.append("weak match")

    return score, reasons


def rank_doc_candidates(
    session,
    title_keywords=None,
    doc_type=None,
    year=None,
    doc_id=None,
    content_hint: str = "",
    limit: int = TOP_CANDIDATES_FOR_LLM,
    hard_limit: int = 300,
) -> list[dict]:
    keywords = clean_keywords(title_keywords)
    normalized_type = normalize_doc_type(doc_type)
    normalized_year = safe_year(year)
    doc_ids = []
    if doc_id:
        doc_ids.append(normalize_doc_id(doc_id))
    doc_ids.extend(extract_doc_ids(content_hint))
    doc_ids = [d for i, d in enumerate(doc_ids) if d and d not in doc_ids[:i]]

    docs = _candidate_query(session, keywords, normalized_type, normalized_year, doc_ids, content_hint, hard_limit)
    ranked = []
    for doc in docs:
        score, reasons = _score_doc(doc, keywords, normalized_type, normalized_year, doc_ids)
        if score > 0:
            ranked.append({"doc": doc, "score": score, "reasons": reasons})

    ranked.sort(key=lambda item: (-item["score"], item["doc"].issue_date or 0, item["doc"].uid))
    return ranked[:limit]


def format_ranked_candidates(ranked_candidates):
    lines = []
    for idx, item in enumerate(ranked_candidates, start=1):
        doc = item["doc"]
        year = doc.issue_date.year if doc.issue_date else "?"
        reasons = "; ".join(item["reasons"][:5])
        lines.append(
            f"{idx}. uid={doc.uid} | score={item['score']} | doc_id={doc.doc_id} | "
            f"title={doc.title} | type={doc.doc_type} | year={year} | reasons={reasons}"
        )
    return "\n".join(lines)


def _extract_params_with_llm(llm, content_hint: str, context_instruction: str = "") -> dict | None:
    extract_prompt = (
        f"{DB_SCHEMA_CONTEXT}\n\n"
        f"Nhiệm vụ: Dựa vào đoạn văn bản dưới đây, xác định văn bản pháp luật được đề cập "
        f"và trả về JSON tham số tìm kiếm.\n"
        f"doc_type chỉ được là một trong 5 giá trị: Luật, Bộ luật, Nghị định, Nghị quyết, Hiến pháp.\n"
        f"{context_instruction}\n\n"
        f"Nội dung:\n\"{content_hint[:1500]}\"\n\n"
        f"Trả về JSON (không thêm gì khác):\n"
        f"{{\"title_keywords\": [\"từ khóa 1\", \"từ khóa 2\"], "
        f"\"doc_type\": \"Luật\", \"year\": 2020, \"doc_id\": null}}\n"
        f"Để null nếu không rõ year, doc_type hoặc doc_id."
    )
    raw = llm.generate(extract_prompt)
    try:
        return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except Exception:
        return None


def _choose_candidate_with_llm(llm, ranked_candidates, content_hint, params, article_numbers=None, context_instruction=""):
    allowed_uids = {item["doc"].uid for item in ranked_candidates}
    confirm_prompt = (
        f"{DB_SCHEMA_CONTEXT}\n\n"
        f"Dưới đây là các candidate đã được truy vấn từ database và xếp hạng bởi code.\n"
        f"Nhiệm vụ: chọn đúng văn bản pháp luật được nhắc tới, hoặc trả null nếu không có candidate đúng.\n"
        f"Chỉ được chọn uid xuất hiện trong danh sách. Không được đoán.\n\n"
        f"{context_instruction}\n\n"
        f"Thông tin đã extract:\n{json.dumps(params, ensure_ascii=False)}\n"
        f"article_numbers cần kiểm tra nếu có: {json.dumps(article_numbers or [], ensure_ascii=False)}\n\n"
        f"Nội dung/căn cứ:\n\"{content_hint[:1200]}\"\n\n"
        f"Candidates:\n{format_ranked_candidates(ranked_candidates)}\n\n"
        f"Trả về duy nhất JSON: {{\"uid\": \"...\"}} hoặc {{\"uid\": null}}"
    )
    raw = llm.generate(confirm_prompt)
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        uid = data.get("uid")
    except Exception:
        uid = raw.strip().strip('"').strip("'")

    if not uid or str(uid).lower() == "null":
        return None
    if uid not in allowed_uids:
        return None
    return next(item for item in ranked_candidates if item["doc"].uid == uid)


def find_doc_agentic(
    session,
    llm,
    content_hint: str = "",
    context_instruction: str = "",
    title_keywords=None,
    doc_type=None,
    year=None,
    doc_id=None,
    article_numbers=None,
) -> dict | None:
    params = {
        "title_keywords": clean_keywords(title_keywords),
        "doc_type": normalize_doc_type(doc_type),
        "year": safe_year(year),
        "doc_id": normalize_doc_id(doc_id),
    }

    if not any(params.values()):
        extracted = _extract_params_with_llm(llm, content_hint, context_instruction)
        if not extracted:
            return None
        params = {
            "title_keywords": clean_keywords(extracted.get("title_keywords")),
            "doc_type": normalize_doc_type(extracted.get("doc_type")),
            "year": safe_year(extracted.get("year")),
            "doc_id": normalize_doc_id(extracted.get("doc_id")),
        }

    ranked = rank_doc_candidates(
        session,
        title_keywords=params["title_keywords"],
        doc_type=params["doc_type"],
        year=params["year"],
        doc_id=params["doc_id"],
        content_hint=content_hint,
        limit=TOP_CANDIDATES_FOR_LLM,
    )
    if not ranked:
        return None

    best = ranked[0]
    second_score = ranked[1]["score"] if len(ranked) > 1 else 0
    if best["score"] >= 160 and best["score"] - second_score >= 50:
        return doc_to_result(best["doc"], best["score"], best["reasons"])

    chosen = _choose_candidate_with_llm(
        llm,
        ranked,
        content_hint,
        params,
        article_numbers=article_numbers,
        context_instruction=context_instruction,
    )
    if not chosen:
        return None
    return doc_to_result(chosen["doc"], chosen["score"], chosen["reasons"])


def _article_number_value(article_number: str | None) -> tuple[int, str] | None:
    if not article_number:
        return None
    match = re.match(r"^(\d+)([a-zA-Z]*)$", str(article_number).strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2).lower()


def get_neighbor_articles(session, doc_uid: str, exclude_article_id: str, count: int = 3) -> list:
    target = session.query(LegalArticle).filter(LegalArticle.article_id == exclude_article_id).first()
    target_value = _article_number_value(target.article_number if target else None)
    articles = (
        session.query(LegalArticle)
        .filter(LegalArticle.doc_uid == doc_uid)
        .filter(LegalArticle.article_id != exclude_article_id)
        .all()
    )
    if not target_value:
        return articles[:count]

    def distance(article):
        value = _article_number_value(article.article_number)
        if not value:
            return (10_000, str(article.article_number))
        return (abs(value[0] - target_value[0]), value[1])

    return sorted(articles, key=distance)[:count]

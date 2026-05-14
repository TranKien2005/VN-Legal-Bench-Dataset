import re
import random
from sqlalchemy.sql import func
from db.models import LegalDoc, LegalArticle

def normalize_legal_text(text: str) -> str:
    """
    Loại bỏ xuống dòng, dấu câu, và các ký hiệu đầu mục (1., a., -) 
    chỉ giữ lại chữ và số để đánh giá truy hồi thuần túy.
    """
    if not text:
        return ""
    
    # 1. Loại bỏ các ký hiệu đầu mục dạng 1., a., i., - (Thực hiện khi còn xuống dòng)
    text = re.sub(r'^\s*([0-9]+|[a-z]+|[ivxldm]+)[\.\)]\s*', ' ', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^\s*-\s*', ' ', text, flags=re.MULTILINE)

    # 2. Thay thế xuống dòng bằng khoảng trắng
    text = text.replace('\n', ' ')
    
    # 3. Loại bỏ mọi dấu câu
    text = re.sub(r'[^\w\s]', '', text)
    
    # 4. Loại bỏ khoảng trắng thừa
    text = " ".join(text.split())
    return text.strip()

def article_number_int(article_number: str | None) -> int | None:
    if not article_number:
        return None
    match = re.match(r"^(\d+)", str(article_number).strip())
    if not match:
        return None
    return int(match.group(1))


def get_doc_article_bounds(session, doc_uid: str) -> tuple[int, int] | None:
    numbers = [
        n for (n,) in session.query(LegalArticle.article_number).filter(LegalArticle.doc_uid == doc_uid).all()
    ]
    parsed = [article_number_int(n) for n in numbers]
    parsed = [n for n in parsed if n is not None]
    if not parsed:
        return None
    return min(parsed), max(parsed)


def is_core_article(session, article: LegalArticle, min_articles_per_doc: int = 8, edge_margin: int = 2) -> bool:
    num = article_number_int(article.article_number)
    if num is None or not article.content or len(article.content.strip()) < 80:
        return False
    bounds = get_doc_article_bounds(session, article.doc_uid)
    if not bounds:
        return False
    first_num, last_num = bounds
    total = last_num - first_num + 1
    if total < min_articles_per_doc:
        return False
    return first_num + edge_margin <= num <= last_num - edge_margin


def filter_core_articles(session, articles: list[LegalArticle], min_articles_per_doc: int = 8, edge_margin: int = 2) -> list[LegalArticle]:
    return [a for a in articles if is_core_article(session, a, min_articles_per_doc, edge_margin)]


def _sample_core_articles(session, query, limit: int) -> list[LegalArticle]:
    if limit <= 0:
        return []
    candidates = query.order_by(func.random()).limit(max(limit * 20, 100)).all()
    return filter_core_articles(session, candidates)[:limit]


def get_stratified_articles(session, limit=50):
    """
    Lấy mẫu điều khoản theo tỷ lệ 80% Luật, 18% Nghị định, 2% Special (HP2013),
    tránh điều đầu/cuối và văn bản có quá ít điều khoản.
    """
    num_laws = int(limit * 0.8)
    num_decrees = int(limit * 0.18)
    num_special = limit - num_laws - num_decrees

    selected_articles = []

    laws_query = session.query(LegalArticle).join(LegalDoc).filter(LegalDoc.doc_type == "Luật")
    selected_articles.extend(_sample_core_articles(session, laws_query, num_laws))

    decrees_query = session.query(LegalArticle).join(LegalDoc).filter(LegalDoc.doc_type == "Nghị định")
    selected_articles.extend(_sample_core_articles(session, decrees_query, num_decrees))

    specials_query = session.query(LegalArticle).join(LegalDoc).filter(LegalDoc.uid == "HP2013")
    specials = _sample_core_articles(session, specials_query, num_special)
    if not specials:
        specials_query = session.query(LegalArticle).join(LegalDoc).filter(LegalDoc.doc_id == "HP2013")
        specials = _sample_core_articles(session, specials_query, num_special)
    selected_articles.extend(specials)

    random.shuffle(selected_articles)
    return selected_articles

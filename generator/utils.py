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
    # Thay thế xuống dòng bằng khoảng trắng
    text = text.replace('\n', ' ')
    # Loại bỏ các ký hiệu đầu mục dạng 1., a., i., - 
    text = re.sub(r'^\s*([0-9]+|[a-z]+)\.?\s*', ' ', text, flags=re.MULTILINE)
    # Loại bỏ mọi dấu câu
    text = re.sub(r'[^\w\s]', '', text)
    # Loại bỏ khoảng trắng thừa
    text = " ".join(text.split())
    return text.strip()

def get_stratified_articles(session, limit=50):
    """
    Lấy mẫu điều khoản theo tỷ lệ 80% Luật, 18% Nghị định, 2% Special (HP2013).
    """
    num_laws = int(limit * 0.8)
    num_decrees = int(limit * 0.18)
    num_special = limit - num_laws - num_decrees
    
    selected_articles = []
    
    # 1. Lấy Luật
    laws = session.query(LegalArticle).join(LegalDoc).filter(
        LegalDoc.doc_type == "Luật"
    ).order_by(func.random()).limit(num_laws).all()
    selected_articles.extend(laws)
    
    # 2. Lấy Nghị định
    decrees = session.query(LegalArticle).join(LegalDoc).filter(
        LegalDoc.doc_type == "Nghị định"
    ).order_by(func.random()).limit(num_decrees).all()
    selected_articles.extend(decrees)
    
    # 3. Lấy Special (HP2013)
    specials = session.query(LegalArticle).join(LegalDoc).filter(
        LegalDoc.uid == "HP2013"
    ).order_by(func.random()).limit(num_special).all()
    # Nếu không tìm thấy bằng UID chính xác, thử lọc theo doc_id
    if not specials:
        specials = session.query(LegalArticle).join(LegalDoc).filter(
            LegalDoc.doc_id == "HP2013"
        ).order_by(func.random()).limit(num_special).all()
        
    selected_articles.extend(specials)
    
    random.shuffle(selected_articles)
    return selected_articles

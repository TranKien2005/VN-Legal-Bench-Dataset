"""
SQLAlchemy models cho VN-Legal-Bench-Dataset.

Tables:
  - legal_docs: Văn bản quy phạm pháp luật (Luật, Nghị định, Thông tư,...)
  - legal_articles: Các điều khoản trong văn bản
  - court_cases: Bản án tòa án
"""
from datetime import date
from sqlalchemy import String, Text, Date, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class LegalDoc(Base):
    """Văn bản quy phạm pháp luật."""
    __tablename__ = "legal_docs"

    # UID tổng hợp: slugify(doc_id + title + issue_date)
    uid: Mapped[str] = mapped_column(String(150), primary_key=True)
    
    # Số hiệu gốc (có thể trùng lặp cho văn bản cũ)
    doc_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(Text)                    # "Luật Giáo dục 2019"
    
    # Chuẩn hóa: "Luật", "Nghị định", "Nghị quyết", "Thông tư",...
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Cơ quan ban hành: "Quốc hội", "Chính phủ",...
    issuing_body: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Trạng thái: "Có", "Không", "Không xác định"
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)          # Full text backup
    
    # Relationships
    articles: Mapped[list["LegalArticle"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LegalDoc {self.uid}: {self.title}>"


class LegalArticle(Base):
    """Điều khoản trong văn bản quy phạm pháp luật."""
    __tablename__ = "legal_articles"

    # VD: "uid_D2"
    article_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    doc_uid: Mapped[str] = mapped_column(
        String(150), ForeignKey("legal_docs.uid"), index=True
    )
    article_number: Mapped[str] = mapped_column(String(20))  # "2", "33a"
    title: Mapped[str | None] = mapped_column(Text)           # Tên điều (nếu có)
    content: Mapped[str] = mapped_column(Text)                 # Nội dung đầy đủ
    is_amendment: Mapped[bool] = mapped_column(default=False)  # Sửa đổi, bổ sung

    # Relationships
    doc: Mapped["LegalDoc"] = relationship(back_populates="articles")

    def __repr__(self) -> str:
        return f"<LegalArticle {self.article_id}>"


class CourtCase(Base):
    """Bản án tòa án (Refined Schema)."""
    __tablename__ = "court_cases"

    # ID rút gọn: [Số hiệu]-[Court Acronym]-[yyyy-mm-dd]
    uid: Mapped[str] = mapped_column(String(150), primary_key=True)
    
    # Thông tin định danh (Ưu tiên lấy từ Raw Text)
    case_number: Mapped[str | None] = mapped_column(String(100), index=True)
    court_name: Mapped[str | None] = mapped_column(String(255))
    issuance_date: Mapped[date | None] = mapped_column(Date)
    
    # Thông tin phân loại
    title_web: Mapped[str | None] = mapped_column(Text)        # Tên từ web
    title_parsed: Mapped[str | None] = mapped_column(Text)     # Tên từ header văn bản
    legal_relation: Mapped[str | None] = mapped_column(String(255))
    court_level: Mapped[str | None] = mapped_column(String(50))
    case_type: Mapped[str | None] = mapped_column(String(100))
    case_info: Mapped[str | None] = mapped_column(Text)
    
    # Nguồn cấp
    source_url: Mapped[str | None] = mapped_column(String(255))
    source_doc_url: Mapped[str | None] = mapped_column(String(255))
    
    # Thành phần chuyên sâu
    summary: Mapped[str | None] = mapped_column(Text)
    legal_bases: Mapped[str | None] = mapped_column(Text)      # Các căn cứ pháp lý trích dẫn
    decision_items: Mapped[list[str] | None] = mapped_column(JSON) # Danh sách quyết định chi tiết
    raw_text: Mapped[str | None] = mapped_column(Text)         # Full text backup
    
    # 4 phần chính (đã tách)
    section_introduction: Mapped[str | None] = mapped_column(Text)
    section_content: Mapped[str | None] = mapped_column(Text)
    section_reasoning: Mapped[str | None] = mapped_column(Text)
    section_decision: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<CourtCase {self.uid}: {self.case_number}>"

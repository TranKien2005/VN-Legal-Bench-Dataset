"""
SQLAlchemy models cho VN-Legal-Bench-Dataset.

Tables:
  - legal_docs: Văn bản quy phạm pháp luật (Luật, Nghị định, Thông tư,...)
  - legal_articles: Các điều khoản trong văn bản
  - court_cases: Bản án tòa án
"""
from datetime import date
from sqlalchemy import String, Text, Date, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class LegalDoc(Base):
    """Văn bản quy phạm pháp luật."""
    __tablename__ = "legal_docs"

    # VD: "43/2019/QH14"
    doc_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(Text)                    # "Luật Giáo dục 2019"
    doc_type: Mapped[str | None] = mapped_column(String(50))    # "Luật"
    issuing_body: Mapped[str | None] = mapped_column(String(100))  # "Quốc hội"
    issue_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    raw_text: Mapped[str | None] = mapped_column(Text)          # Full text backup

    # Relationships
    articles: Mapped[list["LegalArticle"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LegalDoc {self.doc_id}: {self.title}>"


class LegalArticle(Base):
    """Điều khoản trong văn bản quy phạm pháp luật."""
    __tablename__ = "legal_articles"

    # VD: "43/2019/QH14_D2" (doc_id + "_D" + article_number)
    article_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("legal_docs.doc_id"), index=True
    )
    article_number: Mapped[str] = mapped_column(String(20))  # "2", "33a"
    title: Mapped[str | None] = mapped_column(Text)           # Tên điều (nếu có)
    content: Mapped[str] = mapped_column(Text)                 # Nội dung đầy đủ

    # Relationships
    doc: Mapped["LegalDoc"] = relationship(back_populates="articles")

    def __repr__(self) -> str:
        return f"<LegalArticle {self.article_id}>"


class CourtCase(Base):
    """Bản án tòa án."""
    __tablename__ = "court_cases"

    # VD: "122/2026/DS-PT"
    case_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)        # "Tranh chấp hợp đồng tín dụng"
    case_date: Mapped[date | None] = mapped_column(Date)
    raw_text: Mapped[str | None] = mapped_column(Text)     # Full text backup

    # 4 phần chính (đã tách)
    introduction: Mapped[str | None] = mapped_column(Text)     # Phần mở đầu
    case_content: Mapped[str | None] = mapped_column(Text)     # Nội dung vụ án
    court_reasoning: Mapped[str | None] = mapped_column(Text)  # Nhận định của tòa
    decision: Mapped[str | None] = mapped_column(Text)         # Quyết định


    def __repr__(self) -> str:
        return f"<CourtCase {self.case_id}: {self.title}>"

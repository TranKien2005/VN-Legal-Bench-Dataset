"""
Script khởi tạo DB schema và import văn bản quy phạm pháp luật từ PDF.

Usage:
    python scripts/import_legal_docs.py data/raw/legal_docs/
    python scripts/import_legal_docs.py path/to/single_file.pdf
"""
import sys
from pathlib import Path

# Thêm project root vào Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.pdf_parser import extract_text_from_file
from parsers.legal_doc_parser import parse_legal_doc
from db.models import Base, LegalDoc, LegalArticle
from db.session import engine, get_session


def init_db():
    """Tạo tất cả tables nếu chưa tồn tại."""
    Base.metadata.create_all(engine)
    print("✓ Database tables đã sẵn sàng.")


def import_legal_doc(pdf_path: Path, session) -> str | None:
    """
    Import một file PDF văn bản quy phạm vào DB.

    Returns:
        doc_id nếu thành công, None nếu lỗi.
    """
    print(f"\n--- Xử lý: {pdf_path.name} ---")

    # 1. Trích xuất text từ file
    try:
        raw_text = extract_text_from_file(pdf_path)
    except Exception as e:
        print(f"  ✗ Lỗi đọc file: {e}")
        return None

    if not raw_text.strip():
        print("  ✗ PDF rỗng hoặc không trích xuất được text.")
        return None

    # 2. Parse văn bản
    parsed = parse_legal_doc(raw_text)

    if not parsed.doc_id:
        print("  ⚠ Không tìm thấy doc_id (mã số văn bản).")
        print("  Vui lòng kiểm tra file PDF hoặc nhập thủ công.")
        return None

    # 3. Kiểm tra trùng
    existing = session.get(LegalDoc, parsed.doc_id)
    if existing:
        print(f"  ⚠ doc_id '{parsed.doc_id}' đã tồn tại. Bỏ qua.")
        return parsed.doc_id

    # 4. Tạo LegalDoc
    legal_doc = LegalDoc(
        doc_id=parsed.doc_id,
        title=pdf_path.stem,  # User có thể cập nhật title sau
        raw_text=parsed.raw_text,
    )
    session.add(legal_doc)
    print(f"  ✓ doc_id: {parsed.doc_id}")

    # 5. Tạo các LegalArticle
    for article in parsed.articles:
        article_id = f"{parsed.doc_id}_D{article.article_number}"
        legal_article = LegalArticle(
            article_id=article_id,
            doc_id=parsed.doc_id,
            article_number=article.article_number,
            title=article.title,
            content=article.content,
        )
        session.add(legal_article)

    print(f"  ✓ Đã tách được {len(parsed.articles)} điều.")
    return parsed.doc_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_legal_docs.py <path_to_file_or_folder>")
        print("  path có thể là file PDF/TXT đơn hoặc folder chứa nhiều file.")
        sys.exit(1)

    target = Path(sys.argv[1])
    init_db()

    # Tìm tất cả file PDF và TXT
    pdf_files = []
    txt_files = []
    
    if target.is_file() and target.suffix.lower() in [".pdf", ".txt"]:
        files = [target]
        if target.suffix.lower() == ".pdf":
            pdf_files = [target]
        else:
            txt_files = [target]
    elif target.is_dir():
        pdf_files = sorted(target.glob("*.pdf"))
        txt_files = sorted(target.glob("*.txt"))
        files = pdf_files + txt_files
    else:
        print(f"✗ Không hợp lệ: {target}")
        sys.exit(1)

    if not files:
        print(f"Không tìm thấy file PDF hoặc TXT nào trong: {target}")
        sys.exit(1)

    print(f"Tìm thấy {len(files)} file (PDF: {len(pdf_files)}, TXT: {len(txt_files)}).")

    # Import từng file
    session = get_session()
    success_count = 0

    try:
        for file_path in files:
            result = import_legal_doc(file_path, session)
            if result:
                success_count += 1

        session.commit()
        print(f"\n{'='*50}")
        print(f"✓ Import thành công: {success_count}/{len(pdf_files)} văn bản.")
    except Exception as e:
        session.rollback()
        print(f"\n✗ Lỗi: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

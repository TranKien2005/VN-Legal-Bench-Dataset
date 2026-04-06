"""
Script import bản án tòa án từ PDF vào DB.

Usage:
    python scripts/import_cases.py data/raw/court_cases/
    python scripts/import_cases.py path/to/single_case.pdf
"""
import sys
from pathlib import Path
from datetime import date

# Thêm project root vào Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.pdf_parser import extract_text_from_file
from parsers.case_parser import parse_court_case
from db.models import Base, CourtCase
from db.session import engine, get_session


def init_db():
    """Tạo tất cả tables nếu chưa tồn tại."""
    Base.metadata.create_all(engine)
    print("✓ Database tables đã sẵn sàng.")


def parse_date_str(date_str: str | None) -> date | None:
    """Parse 'DD-MM-YYYY' thành date object."""
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        return None


def import_case(pdf_path: Path, session) -> str | None:
    """
    Import một file PDF bản án vào DB.

    Returns:
        case_id nếu thành công, None nếu lỗi.
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

    # 2. Parse bản án
    parsed = parse_court_case(raw_text)

    if not parsed.case_id:
        print("  ⚠ Không tìm thấy case_id (mã bản án).")
        print("  Vui lòng kiểm tra file PDF hoặc nhập thủ công.")
        return None

    # 3. Kiểm tra trùng
    existing = session.get(CourtCase, parsed.case_id)
    if existing:
        print(f"  ⚠ case_id '{parsed.case_id}' đã tồn tại. Bỏ qua.")
        return parsed.case_id

    # 4. Tạo CourtCase
    court_case = CourtCase(
        case_id=parsed.case_id,
        title=parsed.title,
        case_date=parse_date_str(parsed.case_date),
        raw_text=parsed.raw_text,
        introduction=parsed.introduction,
        case_content=parsed.case_content,
        court_reasoning=parsed.court_reasoning,
        decision=parsed.decision,
    )
    session.add(court_case)

    # Print summary
    print(f"  ✓ case_id: {parsed.case_id}")
    print(f"  ✓ title: {parsed.title or '(không xác định)'}")
    print(f"  ✓ date: {parsed.case_date or '(không xác định)'}")

    section_info = []
    if parsed.introduction:
        section_info.append(f"intro={len(parsed.introduction)} chars")
    if parsed.case_content:
        section_info.append(f"content={len(parsed.case_content)} chars")
    if parsed.court_reasoning:
        section_info.append(f"reasoning={len(parsed.court_reasoning)} chars")
    if parsed.decision:
        section_info.append(f"decision={len(parsed.decision)} chars")
    print(f"  ✓ Sections: {', '.join(section_info)}")

    return parsed.case_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_cases.py <path_to_file_or_folder>")
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
            # Note: import_case handles both PDF and TXT via extract_text_from_file
            result = import_case(file_path, session)
            if result:
                success_count += 1

        session.commit()
        print(f"\n{'='*50}")
        print(f"✓ Import thành công: {success_count}/{len(files)} bản án.")
    except Exception as e:
        session.rollback()
        print(f"\n✗ Lỗi: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

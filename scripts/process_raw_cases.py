"""
Xử lý bản án tòa án từ PDF/TXT → JSON structured output.

Pipeline: PDF/TXT → OCR/extract text → parse metadata + tách 4 phần → lưu JSON.

Output:
  data/processed/court_cases/{case_id}.json → metadata + 4 phần bản án

Usage:
    py scripts/process_cases.py                                    # Xử lý tất cả PDF/TXT trong data/raw/court_cases/
    py scripts/process_cases.py data/raw/court_cases/file.pdf      # Xử lý 1 file
    py scripts/process_cases.py data/raw/court_cases/file.txt      # Xử lý 1 file TXT
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.pdf_parser import extract_text_from_file
from parsers.case_parser import parse_court_case
from config.settings import settings


def sanitize_filename(case_id: str) -> str:
    """Chuyển case_id thành tên file hợp lệ: 122/2026/DS-PT → 122_2026_DS-PT."""
    return case_id.replace("/", "_")


def process_single_case(file_path: Path, output_dir: Path) -> dict | None:
    """
    Xử lý 1 file PDF hoặc TXT bản án tòa án.

    Returns:
        Summary dict nếu thành công, None nếu lỗi.
    """
    print(f"\n{'='*60}")
    print(f"📄 Xử lý: {file_path.name}")
    print(f"{'='*60}")

    # 1. Trích xuất text từ file
    try:
        raw_text = extract_text_from_file(file_path)
    except Exception as e:
        print(f"  ✗ Lỗi đọc file: {e}")
        return None

    if not raw_text.strip():
        print("  ✗ File rỗng hoặc không trích xuất được text.")
        return None

    print(f"  ✓ Extracted: {len(raw_text):,} chars")

    # 2. Parse bản án
    parsed = parse_court_case(raw_text)

    if not parsed.case_id:
        print("  ⚠ Không tìm thấy case_id (mã bản án).")
        print("  → Dùng tên file làm case_id tạm.")
        parsed.case_id = file_path.stem

    safe_name = sanitize_filename(parsed.case_id)

    # 3. Hiển thị kết quả parse
    print(f"  ✓ case_id:  {parsed.case_id}")
    print(f"  ✓ title:    {parsed.title or '(không xác định)'}")
    print(f"  ✓ date:     {parsed.case_date or '(không xác định)'}")

    sections_info = {
        "introduction": len(parsed.introduction),
        "case_content": len(parsed.case_content),
        "court_reasoning": len(parsed.court_reasoning),
        "decision": len(parsed.decision),
    }
    print(f"  ✓ Sections:")
    for name, chars in sections_info.items():
        status = "✓" if chars > 0 else "✗"
        print(f"    {status} {name}: {chars:,} chars")

    # 4. Lưu court_cases JSON
    case_data = {
        "case_id": parsed.case_id,
        "title": parsed.title,
        "case_date": parsed.case_date,
        "source_file": file_path.name,
        "raw_text": parsed.raw_text,
        "introduction": parsed.introduction,
        "case_content": parsed.case_content,
        "court_reasoning": parsed.court_reasoning,
        "decision": parsed.decision,
    }

    output_file = output_dir / f"{safe_name}.json"
    output_file.write_text(json.dumps(case_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  💾 Saved: {output_file.name}")

    # 5. Preview nội dung từng section (200 chars đầu)
    print(f"\n  📋 Preview các phần:")
    for section_name in ["introduction", "case_content", "court_reasoning", "decision"]:
        content = getattr(parsed, section_name, "")
        if content:
            preview = content[:200].replace("\n", " ")
            print(f"\n  [{section_name.upper()}]")
            print(f"  {preview}...")
        else:
            print(f"\n  [{section_name.upper()}] (trống)")

    return {
        "case_id": parsed.case_id,
        "title": parsed.title,
        "date": parsed.case_date,
        "source": file_path.name,
        "chars": len(raw_text),
        "sections": sections_info,
    }


def main():
    # Xác định input
    if len(sys.argv) >= 2:
        target = Path(sys.argv[1])
    else:
        target = settings.RAW_DIR / "court_cases"

    # Tìm file PDF/TXT
    if target.is_file() and target.suffix.lower() in [".pdf", ".txt"]:
        files = [target]
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

    # Tạo output dir
    output_dir = settings.PROCESSED_DIR / "court_cases"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Tìm thấy {len(files)} file (PDF/TXT).")
    print(f"Output: {output_dir}")

    # Xử lý từng file
    results = []
    for file_path in files:
        result = process_single_case(file_path, output_dir)
        if result:
            results.append(result)

    # Tổng kết
    print(f"\n{'='*60}")
    print(f"✅ HOÀN THÀNH: {len(results)}/{len(files)} bản án")
    print(f"{'='*60}")
    for r in results:
        filled = sum(1 for v in r["sections"].values() if v > 0)
        print(f"  • {r['case_id']}: \"{r['title'] or 'N/A'}\" | {r['chars']:,} chars | {filled}/4 sections")

    print(f"\n📁 Output: {output_dir}")


if __name__ == "__main__":
    main()

"""
Xử lý văn bản quy phạm pháp luật từ PDF/TXT → JSON structured output.

Pipeline: PDF/TXT → OCR/extract text → parse → lưu JSON theo cấu trúc DB.

Output:
  data/processed/legal_docs/{doc_id}.json       → metadata văn bản
  data/processed/legal_articles/{doc_id}.json   → danh sách các điều khoản

Usage:
    py scripts/process_legal_docs.py                              # Xử lý tất cả PDF/TXT trong data/raw/legal_docs/
    py scripts/process_legal_docs.py data/raw/legal_docs/file.pdf # Xử lý 1 file
    py scripts/process_legal_docs.py data/raw/legal_docs/file.txt # Xử lý 1 file TXT
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.pdf_parser import extract_text_from_file
from parsers.legal_doc_parser import parse_legal_doc
from config.settings import settings


def sanitize_filename(doc_id: str) -> str:
    """Chuyển doc_id thành tên file hợp lệ: 43/2019/QH14 → 43_2019_QH14."""
    return doc_id.replace("/", "_")


def process_single_doc(file_path: Path, output_docs_dir: Path, output_articles_dir: Path) -> dict | None:
    """
    Xử lý 1 file PDF hoặc TXT văn bản quy phạm pháp luật.

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

    # 2. Parse văn bản
    parsed = parse_legal_doc(raw_text)

    if not parsed.doc_id:
        print("  ⚠ Không tìm thấy doc_id (mã số văn bản).")
        print("  → Dùng tên file làm doc_id tạm.")
        parsed.doc_id = file_path.stem
    
    safe_name = sanitize_filename(parsed.doc_id)

    # 3. Lưu legal_docs JSON (metadata + raw text)
    doc_data = {
        "doc_id": parsed.doc_id,
        "title": file_path.stem,  # User có thể cập nhật sau
        "doc_type": None,        # Cần bổ sung thủ công hoặc parse thêm
        "issuing_body": None,    # Cần bổ sung thủ công hoặc parse thêm
        "issue_date": None,
        "effective_date": None,
        "raw_text": raw_text,
        "source_file": file_path.name,
        "total_articles": len(parsed.articles),
    }

    doc_output = output_docs_dir / f"{safe_name}.json"
    doc_output.write_text(json.dumps(doc_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Legal doc saved: {doc_output.name}")

    # 4. Lưu legal_articles JSON
    articles_data = []
    for article in parsed.articles:
        article_id = f"{article.article_number}/{parsed.doc_id}"
        articles_data.append({
            "article_id": article_id,
            "doc_id": parsed.doc_id,
            "article_number": article.article_number,
            "title": article.title,
            "content": article.content,
        })

    articles_output = output_articles_dir / f"{safe_name}.json"
    articles_output.write_text(json.dumps(articles_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Articles saved: {articles_output.name} ({len(articles_data)} điều)")

    # 5. Summary
    summary = {
        "doc_id": parsed.doc_id,
        "source": file_path.name,
        "chars": len(raw_text),
        "articles": len(articles_data),
    }
    print(f"\n  📊 Tổng kết: doc_id={parsed.doc_id}, {len(raw_text):,} chars, {len(articles_data)} điều")
    return summary


def main():
    # Xác định input
    if len(sys.argv) >= 2:
        target = Path(sys.argv[1])
    else:
        target = settings.RAW_DIR / "legal_docs"

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

    # Tạo output dirs
    output_docs_dir = settings.PROCESSED_DIR / "legal_docs"
    output_articles_dir = settings.PROCESSED_DIR / "legal_articles"
    output_docs_dir.mkdir(parents=True, exist_ok=True)
    output_articles_dir.mkdir(parents=True, exist_ok=True)

    print(f"Tìm thấy {len(files)} file (PDF/TXT).")
    print(f"Output: {settings.PROCESSED_DIR}")

    # Xử lý từng file
    results = []
    for file_path in files:
        result = process_single_doc(file_path, output_docs_dir, output_articles_dir)
        if result:
            results.append(result)

    # Tổng kết
    print(f"\n{'='*60}")
    print(f"✅ HOÀN THÀNH: {len(results)}/{len(files)} văn bản")
    print(f"{'='*60}")
    for r in results:
        print(f"  • {r['doc_id']}: {r['chars']:,} chars, {r['articles']} điều")

    print(f"\n📁 Output files:")
    print(f"  Legal docs:     {output_docs_dir}")
    print(f"  Legal articles: {output_articles_dir}")


if __name__ == "__main__":
    main()

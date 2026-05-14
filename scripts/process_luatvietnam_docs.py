import sys
import json
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.legal_doc_parser import clean_luatvietnam_raw_text, parse_legal_doc, is_valid_doc_content
from config.settings import settings


def clean_missing(value):
    if not isinstance(value, str):
        return value
    cleaned = " ".join(value.split())
    if cleaned.lower() in {"đã biết", "đang cập nhật", "chưa rõ"}:
        return None
    return cleaned


def main():
    input_dir = settings.RAW_DIR / "legal_docs"
    output_docs_dir = settings.PROCESSED_DIR / "legal_docs"
    output_docs_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("luatvietnam_*.json"))
    if not files:
        print("Không tìm thấy file raw LuatVietnam nào.")
        return

    print(f"Bắt đầu tinh lọc {len(files)} file LuatVietnam thô...")
    total_docs = 0

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_docs = json.load(f)
        except Exception as e:
            print(f"  ! Bỏ qua {file_path.name}: {e}")
            continue

        refined_docs = []
        for raw_doc in raw_docs:
            raw_text = clean_luatvietnam_raw_text(raw_doc.get("raw_text", ""))
            doc_id = clean_missing(raw_doc.get("Số hiệu") or raw_doc.get("doc_id_raw") or "")
            title_web = clean_missing(raw_doc.get("title_web") or raw_doc.get("title") or "")

            if not is_valid_doc_content(title_web, doc_id) or not raw_text.strip():
                continue

            parsed = parse_legal_doc(
                text=raw_text,
                doc_id=doc_id,
                title_web=title_web,
                doc_type=clean_missing(raw_doc.get("Loại văn bản")) or "Văn bản",
                issuing_body=clean_missing(raw_doc.get("Cơ quan ban hành")),
                field=clean_missing(raw_doc.get("Lĩnh vực")),
                issue_date_str=clean_missing(raw_doc.get("Ngày ban hành")),
                effective_date_str=clean_missing(raw_doc.get("Ngày hiệu lực") or raw_doc.get("Ngày có hiệu lực")),
                signer=clean_missing(raw_doc.get("Người ký")),
                summary=clean_missing(raw_doc.get("summary") or raw_doc.get("Tóm tắt")),
                download_links=raw_doc.get("download_links"),
                url=raw_doc.get("url")
            )

            doc_data = asdict(parsed)
            doc_data.pop("articles", None)
            doc_data.pop("status", None)
            refined_docs.append(doc_data)

        if refined_docs:
            output_file = output_docs_dir / file_path.name
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(refined_docs, f, ensure_ascii=False, indent=2, default=str)
            print(f"  ✓ {file_path.name}: Lưu {len(refined_docs)} văn bản.")
            total_docs += len(refined_docs)

    print(f"\n✅ HOÀN THÀNH: Tổng cộng {total_docs} văn bản LuatVietnam.")


if __name__ == "__main__":
    main()

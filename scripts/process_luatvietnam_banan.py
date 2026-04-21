import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Thêm project root vào path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.case_parser import parse_court_case, parse_date, generate_case_uid
from config.settings import settings



def process_raw_data(raw_json_path):
    """Đọc file raw JSON, parse từng bản án và trả về list dict đã xử lý."""
    with open(raw_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    processed_results = []
    for entry in data:
        raw_text = entry.get("raw_text", "")
        if not raw_text:
            continue
            
        # Sử dụng Parser trung tâm
        parsed = parse_court_case(raw_text)
        
        # Merge với metadata từ web nếu có
        web_meta = entry.get("metadata", {})
        
        # Lấy tiêu đề để lọc
        title = parsed.title or ""
        # Bỏ qua nếu là Án lệ hoặc Đính chính
        if "án lệ" in title.lower() or "đính chính" in title.lower():
            continue

        # Ưu tiên dữ liệu từ parser nhưng fallback về web metadata nếu parser fail
        final_case_no = parsed.case_no or web_meta.get("Số hiệu")
        final_court = parsed.court_name or web_meta.get("Tòa án xét xử")
        
        # Luôn tạo lại UID từ thông tin cuối cùng để đảm bảo tính chính xác cao nhất
        uid = generate_case_uid(final_case_no, final_court, parsed.case_date)

        result = {
            "uid": uid,
            "url": entry.get("url"),
            "case_number": final_case_no,
            "court_name": final_court,
            "issuance_date": parsed.case_date or parse_date(web_meta.get("Ngày ban hành")),
            "title_web": web_meta.get("Tên Bản án"),
            "title_parsed": title,
            "legal_relation": web_meta.get("Quan hệ pháp luật"),
            "court_level": web_meta.get("Cấp xét xử"),
            "case_type": web_meta.get("Lĩnh vực"),
            "case_info": web_meta.get("Thông tin về vụ/việc"),
            "legal_bases": parsed.legal_bases,
            "decision_items": parsed.decision_items,
            "source_doc_url": web_meta.get("docx_url") or web_meta.get("pdf_url"),
            "summary": web_meta.get("summary"),
            "raw_text": raw_text,
            "section_introduction": parsed.introduction,
            "section_content": parsed.case_content,
            "section_reasoning": parsed.court_reasoning,
            "section_decision": parsed.decision
        }
        processed_results.append(result)
        
    return processed_results

if __name__ == "__main__":
    # Nếu có tham số -> xử lý 1 file
    if len(sys.argv) >= 2:
        raw_paths = [Path(sys.argv[1])]
    else:
        # Nếu không -> quét toàn bộ thư mục raw
        raw_dir = settings.RAW_DIR / "court_cases"
        if not raw_dir.exists():
            print(f"Thư mục không tồn tại: {raw_dir}")
            sys.exit(1)
            
        raw_paths = list(raw_dir.glob("*.json"))
        print(f"Tìm thấy {len(raw_paths)} file bản án cần xử lý.")

    total_cases = 0
    for raw_path in raw_paths:
        if not raw_path.exists():
            print(f"Bỏ qua: File không tồn tại {raw_path}")
            continue
            
        try:
            results = process_raw_data(raw_path)
            
            # Lưu kết quả
            output_base = settings.PROCESSED_DIR / "court_cases"
            output_base.mkdir(parents=True, exist_ok=True)
            output_path = output_base / raw_path.name
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
            print(f"✓ {raw_path.name}: Đã xử lý {len(results)} bản án.")
            total_cases += len(results)
        except Exception as e:
            print(f"✗ Lỗi khi xử lý {raw_path.name}: {str(e)}")
            
    print(f"\n✅ HOÀN THÀNH: Tổng cộng đã xử lý {total_cases} bản án.")

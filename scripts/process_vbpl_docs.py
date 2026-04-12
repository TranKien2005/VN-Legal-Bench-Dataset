import sys
import json
from pathlib import Path
from dataclasses import asdict

# Thêm đường dẫn gốc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.legal_doc_parser import parse_legal_doc, is_valid_doc_content
from config.settings import settings

def main():
    input_dir = settings.RAW_DIR / "legal_docs"
    output_docs_dir = settings.PROCESSED_DIR / "legal_docs"
    output_docs_dir.mkdir(parents=True, exist_ok=True)
    
    files = sorted(input_dir.glob("vanbanphapluat_*.json"))
    if not files:
        print(f"Không tìm thấy file raw nào.")
        return
        
    print(f"Bắt đầu tinh lọc {len(files)} file dữ liệu thô...")
    total_docs = 0
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_docs = json.load(f)
        except: continue
            
        refined_docs = []
        for raw_doc in raw_docs:
            raw_text = raw_doc.get("raw_text", "")
            so_hieu = raw_doc.get("Số hiệu") or raw_doc.get("doc_id_raw") or ""
            title_web = raw_doc.get("title_web", "")
            
            # 1. Gọi bộ lọc nghiệp vụ từ Parser
            if not is_valid_doc_content(title_web, so_hieu) or not raw_text.strip():
                continue
                
            # 2. Gọi bộ giải mã trung tâm (Tự động chuẩn hóa tiêu đề và tạo UID)
            parsed = parse_legal_doc(
                text=raw_text,
                doc_id=so_hieu,
                title_web=title_web,
                doc_type=raw_doc.get("Loại văn bản") or "Văn bản",
                issuing_body=raw_doc.get("Cơ quan ban hành"),
                field=raw_doc.get("Lĩnh vực"),
                issue_date_str=raw_doc.get("Ngày ban hành"),
                effective_date_str=raw_doc.get("Ngày hiệu lực"),
                status_str=raw_doc.get("Tình trạng hiệu lực"),
                url=raw_doc.get("url")
            )
            
            # 3. Chuẩn bị dữ liệu tinh gọn (giữ raw_text để tách điều khoản sau này)
            doc_data = asdict(parsed)
            doc_data.pop("articles", None)
            
            refined_docs.append(doc_data)
            
        if refined_docs:
            output_file = output_docs_dir / file_path.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(refined_docs, f, ensure_ascii=False, indent=2, default=str)
            print(f"  ✓ {file_path.name}: Lưu {len(refined_docs)} văn bản.")
            total_docs += len(refined_docs)
            
    print(f"\n✅ HOÀN THÀNH: Tổng cộng {total_docs} văn bản chính quy.")

if __name__ == "__main__":
    main()
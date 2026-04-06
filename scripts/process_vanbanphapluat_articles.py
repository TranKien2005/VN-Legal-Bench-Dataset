import sys
import json
import re
from pathlib import Path

# Thêm đường dẫn gốc để import parser và config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.legal_doc_parser import parse_legal_doc
from config.settings import settings

def main():
    # Thư mục chứa các file json được scrape từ vanbanphapluat
    input_dir = settings.PROCESSED_DIR
    target_pattern = "vanbanphapluat_luat_page_*.json"
    
    # Thư mục lưu kết quả (legal_articles)
    output_articles_dir = settings.PROCESSED_DIR / "legal_articles"
    output_articles_dir.mkdir(parents=True, exist_ok=True)
    
    # Quét tất cả file hợp lệ
    files = sorted(input_dir.glob(target_pattern))
    
    if not files:
        print(f"Không tìm thấy file nào khớp mẫu '{target_pattern}' trong {input_dir}")
        sys.exit(1)
        
    print(f"Tìm thấy {len(files)} file trang dữ liệu.")
    print(f"Output folder: {output_articles_dir}")
    
    total_docs = 0
    total_articles = 0
    
    for file_path in files:
        print(f"\n{'='*60}")
        print(f"📄 Xử lý: {file_path.name}")
        
        # Load danh sách văn bản (legal docs) từ file scraping
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                docs = json.load(f)
        except Exception as e:
            print(f"  ✗ Lỗi đọc file {file_path.name}: {e}")
            continue
            
        page_articles_data = []
        page_doc_count = 0
        
        for doc in docs:
            doc_id = doc.get("doc_id", "Unknown")
            raw_text = doc.get("raw_text", "")
            
            if not raw_text.strip():
                print(f"  ⚠ {doc_id}: Không có nội dung raw_text, bỏ qua.")
                continue
                
            # Parse nội dung để lấy Điều/Khoản
            parsed = parse_legal_doc(raw_text)
            
            # Ghi nhận id nếu text không tự parse được
            actual_doc_id = parsed.doc_id if parsed.doc_id else doc_id
            
            doc_articles = 0
            for article in parsed.articles:
                article_id = f"{article.article_number}/{actual_doc_id}"
                page_articles_data.append({
                    "article_id": article_id,
                    "doc_id": actual_doc_id,
                    "article_number": article.article_number,
                    "title": article.title,
                    "content": article.content,
                })
                doc_articles += 1
                
            print(f"  ✓ {actual_doc_id}: bóc tách được {doc_articles} điều")
            page_doc_count += 1
            
        # Lấy tên file tương ứng (ví dụ: đổi đuôi, hoặc giữ nguyên tạo mới trong folder khác)
        # vanbanphapluat_luat_page_1.json -> output/legal_articles/vanbanphapluat_luat_page_1.json
        output_file = output_articles_dir / file_path.name
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(page_articles_data, f, ensure_ascii=False, indent=2)
            print(f"  => Đã lưu thành công {len(page_articles_data)} điều khoản vào: {output_file.name}")
        except Exception as e:
            print(f"  ✗ Lỗi lưu file: {e}")
            
        total_docs += page_doc_count
        total_articles += len(page_articles_data)
        
    print(f"\n{'='*60}")
    print(f"✅ HOÀN THÀNH TẤT CẢ TỆP!")
    print(f"Tóm tắt: Đã quét {total_docs} văn bản, thu hoạch được tổng cộng {total_articles} điều khoản.")
    print(f"Đường dẫn lưu trữ: {output_articles_dir}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

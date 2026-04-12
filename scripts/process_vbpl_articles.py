import sys
import json
from pathlib import Path
from dataclasses import asdict

# Thêm đường dẫn gốc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.legal_doc_parser import split_articles
from config.settings import settings

def main():
    input_refined_dir = settings.PROCESSED_DIR / "legal_docs"
    output_articles_dir = settings.PROCESSED_DIR / "legal_articles"
    output_articles_dir.mkdir(parents=True, exist_ok=True)
    
    files = sorted(input_refined_dir.glob("vanbanphapluat_*.json"))
    if not files:
        print(f"Không tìm thấy file refined nào.")
        return
        
    print(f"Bắt đầu trích xuất Điều khoản từ {len(files)} file trang (Refined)...")
    total_articles = 0
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                docs = json.load(f)
        except: continue
            
        page_articles = []
        for doc in docs:
            raw_text = doc.get("raw_text", "")
            doc_id = doc.get("doc_id", "")
            doc_uid = doc.get("uid", "")
            is_amendment = doc.get("is_amendment", False)
            
            if not raw_text or not doc_id or not doc_uid:
                continue
                
            # 1. Gọi bộ tách Điều khoản tập trung (Tự động gán article_id và article_uid)
            articles = split_articles(raw_text, doc_id, doc_uid, is_amendment)
            
            for art in articles:
                page_articles.append(asdict(art))
            
            if articles:
                print(f"  ✓ {doc_id}: {len(articles)} điều.")
            
        if page_articles:
            output_file = output_articles_dir / file_path.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(page_articles, f, ensure_ascii=False, indent=2)
            total_articles += len(page_articles)
            
    print(f"\n✅ HOÀN THÀNH: Đã bóc tách {total_articles} điều khoản với định danh duy nhất.")

if __name__ == "__main__":
    main()

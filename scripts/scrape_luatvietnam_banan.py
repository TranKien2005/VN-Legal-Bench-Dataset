import argparse
import sys
import json
import time
import random
import re
from pathlib import Path
from datetime import datetime

# Thêm project root vào path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from scrapers.luatvietnam_engine import LuatVietnamEngine

def slugify(text):
    """Bỏ dấu tiếng Việt và thay khoảng trắng bằng gạch dưới."""
    import unicodedata
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def run_topic_mode(engine, topics_file, target_per_topic=10):
    """Chạy cào dữ liệu theo chủ đề và từ khóa với quota."""
    if not Path(topics_file).exists():
        print(f"[LỖI] Không tìm thấy file cấu hình: {topics_file}")
        return

    with open(topics_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    topics = data.get("topics", [])
    print(f"=== CHẾ ĐỘ CÀO THEO CHỦ ĐỀ: {len(topics)} chủ đề, mục tiêu {target_per_topic} bản án/chủ đề ===")
    
    for topic in topics:
        topic_name = topic["name"]
        topic_id = topic["id"]
        keywords = topic["keywords"]
        
        print(f"\n>>> XỬ LÝ CHỦ ĐỀ: {topic_name} (ID: {topic_id})")
        
        topic_count = 0
        keyword_targets = {}
        
        # Chia đều target cho các keyword ban đầu
        base_target = target_per_topic // len(keywords)
        remainder = target_per_topic % len(keywords)
        
        for i, kw in enumerate(keywords):
            keyword_targets[kw] = base_target + (1 if i < remainder else 0)

        for kw in keywords:
            if topic_count >= target_per_topic:
                break
                
            current_target = keyword_targets[kw]
            if current_target <= 0:
                continue
                
            print(f"  [*] Từ khóa: '{kw}' (Mục tiêu cho từ khóa: {current_target})")
            kw_results = []
            page = 1
            
            while len(kw_results) < current_target:
                params = {
                    "SearchKeyword": kw,
                    "DateFrom": "", # Không giới hạn thời gian
                    "DateTo": "",
                    "JudicialLevelId": "1", # Mặc định sơ thẩm
                    "LawJudgTypeId": "1",
                    "Page": page
                }
                
                search_results = engine.scrape_search_page(params)
                if not search_results:
                    print(f"    [!] Hết kết quả cho từ khóa '{kw}' tại trang {page}.")
                    break
                
                # Lọc tiêu đề chứa keyword (không phân biệt hoa thường)
                filtered_results = []
                for res in search_results:
                    if kw.lower() in res["title"].lower():
                        filtered_results.append(res)
                    else:
                        # Log nhẹ để biết đang lọc
                        pass

                for res in filtered_results:
                    if len(kw_results) >= current_target:
                        break
                    
                    print(f"    [*] Đang tải {len(kw_results)+1}/{current_target}: {res['url']}")
                    doc = engine.scrape_detail_page(res["url"])
                    if doc:
                        kw_results.append(doc)
                        topic_count += 1
                    time.sleep(random.uniform(1, 2))
                
                page += 1
                if page > 15: # Giới hạn trang tối đa cho 1 keyword
                    break
            
            # Lưu kết quả theo từ khóa
            if kw_results:
                kw_slug = slugify(kw)
                filename = f"luatvietnam_{topic_id}_{kw_slug}____.json"
                output_path = engine.raw_dir / filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(kw_results, f, ensure_ascii=False, indent=2)
                print(f"    [OK] Đã lưu {len(kw_results)} bản án vào {filename}")
            
            # Nếu không đủ quota, chuyển phần dư sang keyword tiếp theo trong cùng chủ đề
            if len(kw_results) < current_target:
                deficit = current_target - len(kw_results)
                idx = keywords.index(kw)
                if idx + 1 < len(keywords):
                    keyword_targets[keywords[idx+1]] += deficit
                    print(f"    [!] Chuyển {deficit} chỉ tiêu còn thiếu sang từ khóa tiếp theo.")

        print(f">>> Hoàn tất chủ đề {topic_name}: Tổng cộng {topic_count}/{target_per_topic} bản án.")

def main():
    parser = argparse.ArgumentParser(description="Scraper bản án từ LuatVietnam.vn")
    # Chế độ cũ
    parser.add_argument("--pages", type=int, default=1, help="Số lượng trang cần cào (chế độ thường)")
    parser.add_argument("--start", type=int, default=1, help="Trang bắt đầu (chế độ thường)")
    parser.add_argument("--keyword", type=str, default="", help="Từ khóa tìm kiếm (chế độ thường)")
    
    # Chế độ theo chủ đề (Mới)
    parser.add_argument("--topic_mode", action="store_true", help="Kích hoạt cào theo chủ đề từ config")
    parser.add_argument("--topics_file", type=str, default="config/search_topics.json", help="Đường dẫn file topics")
    parser.add_argument("--quota", type=int, default=10, help="Số lượng bản án mục tiêu cho mỗi chủ đề")
    
    # Cấu hình chung
    parser.add_argument("--workers", type=int, default=1, help="Số lượng worker")
    parser.add_argument("--date_from", type=str, default="", help="Ngày bắt đầu (dd/mm/yyyy)")
    parser.add_argument("--date_to", type=str, default="", help="Ngày kết thúc (dd/mm/yyyy)")
    
    args = parser.parse_args()

    engine = LuatVietnamEngine(num_workers=args.workers)

    if args.topic_mode:
        run_topic_mode(engine, args.topics_file, target_per_topic=args.quota)
    else:
        print(f"=== CHẾ ĐỘ CÀO THÔNG THƯỜNG ===")
        custom_params = {
            "SearchKeyword": args.keyword,
            "DateFrom": args.date_from,
            "DateTo": args.date_to,
            "JudicialLevelId": "1",
            "LawJudgTypeId": "1"
        }
        engine.run(max_pages=args.pages, start_page=args.start, custom_params=custom_params)

if __name__ == "__main__":
    main()

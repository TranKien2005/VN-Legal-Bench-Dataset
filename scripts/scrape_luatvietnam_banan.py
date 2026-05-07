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
    if not text: return "empty"
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

def run_unified_scraper(engine, topics_file, total_target=300):
    """
    Chạy cào dữ liệu hợp nhất: Chia đều cho 14 topic từ file + 1 topic Discovery.
    Không lấy bù quota, không giới hạn số trang.
    """
    if not Path(topics_file).exists():
        print(f"[LỖI] Không tìm thấy file cấu hình: {topics_file}")
        return

    with open(topics_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    topics = data.get("topics", [])
    
    # Thêm topic thứ 15: Discovery (Không keyword)
    topics.append({
        "id": "DISCOVERY",
        "name": "Khám phá ngẫu nhiên",
        "keywords": [""] # Keyword rỗng để lấy bản án mới nhất
    })

    num_topics = len(topics)
    target_per_topic = total_target // num_topics
    
    print(f"=== CHẾ ĐỘ CÀO HỢP NHẤT: {num_topics} chủ đề, mục tiêu {target_per_topic} bản án/chủ đề ===")
    print(f"=== Tổng mục tiêu: ~{num_topics * target_per_topic} bản án ===")

    for topic in topics:
        topic_name = topic["name"]
        topic_id = topic["id"]
        keywords = topic["keywords"]
        
        print(f"\n>>> XỬ LÝ CHỦ ĐỀ: {topic_name} (ID: {topic_id})")
        
        topic_count = 0
        # Chia đều target của topic cho các keyword bên trong
        target_per_kw = target_per_topic // len(keywords)
        
        for kw in keywords:
            if topic_count >= target_per_topic:
                break
                
            print(f"  [*] Từ khóa: '{kw if kw else '[TRỐNG]'}' (Mục tiêu: {target_per_kw})")
            kw_results = []
            page = 1
            consecutive_empty_pages = 0
            
            # Vòng lặp cho đến khi đủ số lượng hoặc hết kết quả/bị kẹt
            while len(kw_results) < target_per_kw:
                params = {
                    "SearchKeyword": kw,
                    "JudicialLevelId": "1",
                    "LawJudgTypeId": "1",
                    "Page": page
                }
                
                search_results = engine.scrape_search_page(params)
                if not search_results:
                    print(f"    [!] Hết kết quả trên web tại trang {page}.")
                    break
                
                # LỌC MỜ TRÊN TIÊU ĐỀ (Độ tương đồng >= 70%)
                filtered_results = []
                for res in search_results:
                    if not kw:
                        filtered_results.append(res)
                        continue
                        
                    title_words = set(res["title"].lower().split())
                    kw_words = set(kw.lower().split())
                    
                    # Tính tỷ lệ từ trùng lặp
                    overlap = kw_words.intersection(title_words)
                    similarity = len(overlap) / len(kw_words) if kw_words else 1.0
                    
                    if similarity >= 0.7:
                        filtered_results.append(res)
                
                if not filtered_results:
                    print(f"    [!] Không có kết quả phù hợp tiêu đề tại trang {page}. Thử trang tiếp theo.")
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= 10:
                        print(f"    [!] Đã 10 trang liên tiếp không thấy kết quả phù hợp tiêu đề. Bỏ qua từ khóa '{kw}'.")
                        break
                    page += 1
                    continue

                # Tải trang chi tiết song song
                found_in_page = 0
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=engine.num_workers) as executor:
                    futures = [executor.submit(engine.scrape_detail_page, res["url"]) for res in filtered_results]
                    for future in futures:
                        if len(kw_results) >= target_per_kw:
                            break
                        doc = future.result()
                        if doc:
                            kw_results.append(doc)
                            topic_count += 1
                            found_in_page += 1
                
                if found_in_page > 0:
                    consecutive_empty_pages = 0 # Reset nếu tìm thấy
                else:
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= 10:
                        print(f"    [!] Đã 10 trang liên tiếp không tải được bản án đạt chuẩn (>1000 ký tự). Bỏ qua từ khóa '{kw}'.")
                        break

                print(f"    [+] Trang {page}: Đã lấy được {len(kw_results)}/{target_per_kw}")
                page += 1
                # Nghỉ nhẹ giữa các trang để tránh bị block
                time.sleep(random.uniform(1, 3))
            
            # Lưu kết quả của từ khóa này
            if kw_results:
                kw_slug = slugify(kw)
                filename = f"luatvietnam_{topic_id}_{kw_slug}____.json"
                output_path = engine.raw_dir / filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(kw_results, f, ensure_ascii=False, indent=2)
                print(f"    [OK] Đã lưu {len(kw_results)} bản án vào {filename}")
            
            # KHÔNG lấy bù quota (Yêu cầu của USER)

        print(f">>> Hoàn tất chủ đề {topic_name}: Tổng cộng {topic_count} bản án.")

def main():
    parser = argparse.ArgumentParser(description="Scraper bản án hợp nhất từ LuatVietnam.vn")
    parser.add_argument("--total_quota", type=int, default=300, help="Tổng số lượng bản án mục tiêu (chia đều cho 15 nhóm)")
    parser.add_argument("--topics_file", type=str, default="config/search_topics.json", help="Đường dẫn file cấu hình 14 topics")
    parser.add_argument("--workers", type=int, default=3, help="Số lượng worker chạy song song")
    
    args = parser.parse_args()

    engine = LuatVietnamEngine(num_workers=args.workers)
    
    # Chạy quy trình hợp nhất
    run_unified_scraper(engine, args.topics_file, total_target=args.total_quota)

if __name__ == "__main__":
    main()

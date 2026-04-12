import asyncio
import json
import sys
from pathlib import Path

# Thêm đường dẫn gốc để import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.vbpl_engine import setup_browser, scrape_page_task
from config.settings import settings

async def main():
    # --- DANH SÁCH LINK CẦN CÀO ĐẶC BIỆT ---
    urls_to_scrape = [
        "https://vanbanphapluat.co/luat-dat-dai-2024",
        # Thêm các link khác tại đây...
    ]
    # ---------------------------------------

    if not urls_to_scrape:
        print("Vui lòng nhập danh sách URL vào biến urls_to_scrape trong script.")
        return

    browser, context = await setup_browser()
    if not browser:
        print("Không thể kết nối Chrome (9222). Hãy đảm bảo Chrome đang mở với --remote-debugging-port=9222")
        return

    output_dir = settings.RAW_DIR / "special_docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=== SCRAPING ĐẶC BIỆT ({len(urls_to_scrape)} văn bản) ===")
    
    results = []
    for i, url in enumerate(urls_to_scrape):
        print(f"[{i+1}/{len(urls_to_scrape)}] Đang xử lý: {url}")
        
        # Giả lập một page_item tối giản để tái sử dụng scrape_page_task
        # Chúng ta chỉ cần link, còn title/doc_id sẽ được scrape_page_task tự trích xuất từ bảng metadata trên trang
        fake_page_item = {
            "link": url,
            "title": "Special Extraction",
            "doc_id": "PENDING"
        }
        
        try:
            # Re-use the existing robust scraper task
            res = await scrape_page_task(context, fake_page_item, i)
            if res:
                results.append(res)
                print(f"  ✓ Thành công: {res.get('doc_id')}")
            else:
                print(f"  ✗ Bị bộ lọc từ chối hoặc lỗi tải: {url}")
        except Exception as e:
            print(f"  ! Lỗi hệ thống: {e}")

    if results:
        output_file = output_dir / "vanbanphapluat_special_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Đã lưu {len(results)} văn bản vào: {output_file}")
    else:
        print("\nKhông có dữ liệu nào được thu thập.")

    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

import argparse
import sys
import asyncio
from pathlib import Path

# Thêm đường dẫn gốc để import scraper
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scrapers.vbpl_engine import scrape_vanbanphapluat

async def main():
    parser = argparse.ArgumentParser(description="Script chuyên biệt cào NGHỊ ĐỊNH từ vanbanphapluat.co")
    parser.add_argument(
        "--pages", 
        type=str, 
        default="auto", 
        help="Số lượng trang muốn cào (số hoặc 'auto' để tự động tìm)"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Trang bắt đầu cào (mặc định là 1)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Số lượng luồng cào đồng thời (mặc định là 3)"
    )
    
    args = parser.parse_args()
    
    print(f"=== SCRAPING NGHỊ ĐỊNH TỪ VBPL ===")
    print(f"Bắt đầu từ trang: {args.start}")
    print(f"Số trang yêu cầu: {args.pages}")
    print(f"Số luồng: {args.workers}")
    
    try:
        # Sử dụng loại 'nghi-dinh' cho script này
        await scrape_vanbanphapluat(max_pages=args.pages, doc_type_slug="nghi-dinh", start_page=args.start, num_workers=args.workers)
        print("\nHoàn thành!")
    except Exception as e:
        print(f"\nLỗi: {e}")

if __name__ == "__main__":
    asyncio.run(main())

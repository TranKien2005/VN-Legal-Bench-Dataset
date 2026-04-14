import asyncio
import sys
from pathlib import Path

# Thêm đường dẫn gốc để import scraper
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from scrapers.vbpl_engine import scrape_special_vbpl

async def main():
    # --- DANH SÁCH LINK CẦN CÀO ĐẶC BIỆT ---
    urls_to_scrape = [
        "https://vanbanphapluat.co/hien-phap-nam-2013",
        "https://vanbanphapluat.co/nghi-quyet-326-2016-ubtvqh14-muc-thu-mien-giam-thu-nop-quan-ly-su-dung-an-phi-le-phi-toa-an"
    ]
    # ---------------------------------------

    if not urls_to_scrape:
        print("Vui lòng nhập danh sách URL vào biến urls_to_scrape trong script.")
        return

    try:
        # Gọi hàm chuyên biệt từ engine
        await scrape_special_vbpl(urls_to_scrape)
        print("\n[OK] Hoan thanh quy trinh cao dac biet!")
    except Exception as e:
        print(f"\n[LOI] Loi he thong: {e}")

if __name__ == "__main__":
    asyncio.run(main())

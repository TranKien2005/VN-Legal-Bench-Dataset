import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from scrapers.luatvietnam_engine import LuatVietnamLegalDocEngine


urls_to_scrape = [
    "https://luatvietnam.vn/tu-phap/hien-phap-nam-1946-29476-d1.html,"
    "https://luatvietnam.vn/tu-phap/hien-phap-nam-1960-987-d1.html",
    "https://luatvietnam.vn/tu-phap/hien-phap-nam-1980-1072-d1.html",
    "https://luatvietnam.vn/tu-phap/hien-phap-68-lct-hdnn8-quoc-hoi-2351-d1.html",
    "https://luatvietnam.vn/tu-phap/hien-phap-2013-83320-d1.html",
    "https://luatvietnam.vn/thue/nghi-quyet-326-2016-nq-ubtvqh14-uy-ban-thuong-vu-quoc-hoi-112209-d1.html",

    ]


def main():
    if not urls_to_scrape:
        print("Vui lòng nhập danh sách URL vào biến urls_to_scrape trong script.")
        return

    engine = LuatVietnamLegalDocEngine(num_workers=1)
    engine.scrape_special_urls(urls_to_scrape)


if __name__ == "__main__":
    main()

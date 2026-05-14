import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from scrapers.luatvietnam_engine import LuatVietnamLegalDocEngine


def main():
    parser = argparse.ArgumentParser(description="Cào văn bản LUẬT và BỘ LUẬT từ LuatVietnam.vn")
    parser.add_argument("--pages", type=str, default="auto", help="Số trang muốn cào hoặc 'auto'")
    parser.add_argument("--start", type=int, default=1, help="Trang bắt đầu cào")
    parser.add_argument("--workers", type=int, default=3, help="Số worker tải trang chi tiết")
    args = parser.parse_args()

    engine = LuatVietnamLegalDocEngine(num_workers=args.workers)
    engine.run(doc_type_ids=[10, 58], output_prefix="luat", max_pages=args.pages, start_page=args.start)


if __name__ == "__main__":
    main()

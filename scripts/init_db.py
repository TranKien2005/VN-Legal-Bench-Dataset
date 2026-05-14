"""
Script khởi tạo DB schema.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --reset
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from db.models import Base
from db.session import engine


def main():
    parser = argparse.ArgumentParser(description="Khởi tạo DB schema.")
    parser.add_argument("--reset", action="store_true", help="Xóa toàn bộ bảng hiện có rồi tạo lại schema")
    args = parser.parse_args()

    if args.reset:
        print("Dropping existing database tables...")
        Base.metadata.drop_all(engine)

    print("Creating database tables...")
    Base.metadata.create_all(engine)
    print("✓ All tables created successfully!")
    print("  - legal_docs")
    print("  - legal_articles")
    print("  - court_cases")


if __name__ == "__main__":
    main()

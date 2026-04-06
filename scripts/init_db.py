"""
Script khởi tạo DB schema (tạo tất cả tables).

Usage:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import Base
from db.session import engine


def main():
    print("Đang tạo database tables...")
    Base.metadata.create_all(engine)
    print("✓ Tất cả tables đã được tạo thành công!")
    print("  - legal_docs")
    print("  - legal_articles")
    print("  - court_cases")


if __name__ == "__main__":
    main()

"""
Unified Data Import Script for VN-Legal-Bench-Dataset.
Imports LegalDocs, LegalArticles, and CourtCases into PostgreSQL with Delete + Re-import or Upsert logic.
"""
import os
import json
import logging
import argparse
from pathlib import Path
from datetime import date
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal
from db.models import LegalDoc, LegalArticle, CourtCase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None

def clear_table(session: Session, model):
    """Xóa toàn bộ dữ liệu mẫu bản ghi của bảng tương ứng."""
    logger.info(f"🗑️ Đang xóa toàn bộ dữ liệu bảng: {model.__tablename__}...")
    session.query(model).delete()
    session.commit()

def import_legal_docs(session: Session, data_dir: Path, clear: bool = False):
    if clear:
        clear_table(session, LegalDoc)
        
    logger.info("📥 Importing Legal Documents...")
    files = list(data_dir.glob("*.json"))
    count = 0
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
                # Validation: Các trường định danh bắt buộc
                uid = item.get("uid")
                doc_id = item.get("doc_id")
                title = item.get("title")
                
                if not uid or not doc_id or not title:
                    logger.warning(f"⚠️ Bỏ qua LegalDoc {uid}: Thiếu trường định danh (uid, doc_id hoặc title).")
                    continue

                # Map JSON fields to DB columns
                issue_date = item.get("issue_date") or item.get("Ngày ban hành")
                if issue_date == "unknown" or not issue_date:
                    issue_date = None

                stmt = insert(LegalDoc).values(
                    uid=uid,
                    doc_id=doc_id,
                    title=title,
                    doc_type=item.get("doc_type"),
                    issuing_body=item.get("issuing_body"),
                    issue_date=parse_date(issue_date),
                    effective_date=parse_date(item.get("effective_date") or item.get("Ngày có hiệu lực")),
                    status=item.get("status") or item.get("Tình trạng hiệu lực"),
                    url=item.get("url"),
                    raw_text=item.get("raw_text")
                )
                
                # Upsert on conflict of uid
                stmt = stmt.on_conflict_do_update(
                    index_elements=['uid'],
                    set_={
                        "title": stmt.excluded.title,
                        "status": stmt.excluded.status,
                        "url": stmt.excluded.url,
                        "raw_text": stmt.excluded.raw_text
                    }
                )
                session.execute(stmt)
                count += 1
    session.commit()
    logger.info(f"✓ Đã import/cập nhật {count} Legal Documents.")

def import_legal_articles(session: Session, data_dir: Path, clear: bool = False):
    if clear:
        clear_table(session, LegalArticle)
        
    logger.info("📥 Importing Legal Articles...")
    files = list(data_dir.glob("*.json"))
    count = 0
    
    # Lấy danh sách các UID văn bản đã tồn tại trong DB để check khóa ngoại
    existing_docs = {uid[0] for uid in session.query(LegalDoc.uid).all()}
    
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
                doc_uid = item.get("doc_uid")
                # BỎ QUA nếu văn bản cha không tồn tại trong DB (do đã bị lọc ở bước trước)
                if doc_uid not in existing_docs:
                    continue

                # Validation: Nội dung điều luật
                article_id = item.get("article_uid") or item.get("article_id")
                content = item.get("content")
                art_num = item.get("article_number")
                
                if not article_id or not content or str(content).strip() == "" or not art_num:
                    logger.warning(f"⚠️ Bỏ qua LegalArticle {article_id}: Thiếu nội dung hoặc số điều.")
                    continue

                # article_id in DB corresponds to article_uid in JSON for uniqueness
                stmt = insert(LegalArticle).values(
                    article_id=article_id,
                    doc_uid=item.get("doc_uid"),
                    article_number=art_num,
                    title=item.get("title"),
                    content=content,
                    is_amendment=item.get("is_amendment", False)
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=['article_id'],
                    set_={
                        "title": stmt.excluded.title,
                        "content": stmt.excluded.content,
                        "is_amendment": stmt.excluded.is_amendment
                    }
                )
                session.execute(stmt)
                count += 1
    session.commit()
    logger.info(f"✓ Đã import/cập nhật {count} Legal Articles.")

def import_court_cases(session: Session, data_dir: Path, clear: bool = False):
    if clear:
        clear_table(session, CourtCase)
        
    logger.info("📥 Importing Court Cases...")
    files = list(data_dir.glob("*.json"))
    count = 0
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
                # Validation: Phải đủ 4 phần quan trọng của một bản án
                sections = [
                    item.get("section_introduction"),
                    item.get("section_content"),
                    item.get("section_reasoning"),
                    item.get("section_decision")
                ]
                
                # Metadata và Quyết định (Bắt buộc cho Task 3.1)
                title = item.get("title_parsed") or item.get("title_web")
                legal_rel = item.get("legal_relation")
                decisions = item.get("decision_items")
                legal_bases = item.get("legal_bases")

                if any(s is None or str(s).strip() == "" for s in sections):
                    # logger.warning(f"⚠️ Bỏ qua CourtCase {item.get('uid')}: Thiếu phần cấu trúc.")
                    continue

                # Map JSON fields (aligned with 17+ fields recently restored)
                stmt = insert(CourtCase).values(
                    uid=item.get("uid"),
                    case_number=item.get("case_number"),
                    court_name=item.get("court_name"),
                    issuance_date=parse_date(item.get("issuance_date")),
                    title_web=item.get("title_web"),
                    title_parsed=item.get("title_parsed"),
                    legal_relation=item.get("legal_relation"),
                    court_level=item.get("court_level"),
                    case_type=item.get("case_type"),
                    case_info=item.get("case_info"),
                    source_url=item.get("url"),
                    source_doc_url=item.get("source_doc_url"),
                    summary=item.get("summary"),
                    legal_bases=item.get("legal_bases"),
                    decision_items=item.get("decision_items"),
                    raw_text=item.get("raw_text"),
                    section_introduction=item.get("section_introduction"),
                    section_content=item.get("section_content"),
                    section_reasoning=item.get("section_reasoning"),
                    section_decision=item.get("section_decision")
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=['uid'],
                    set_={
                        "case_number": stmt.excluded.case_number,
                        "issuance_date": stmt.excluded.issuance_date,
                        "legal_bases": stmt.excluded.legal_bases,
                        "decision_items": stmt.excluded.decision_items,
                        "summary": stmt.excluded.summary,
                        "section_introduction": stmt.excluded.section_introduction,
                        "section_content": stmt.excluded.section_content,
                        "section_reasoning": stmt.excluded.section_reasoning,
                        "section_decision": stmt.excluded.section_decision
                    }
                )
                session.execute(stmt)
                count += 1
    session.commit()
    logger.info(f"✓ Đã import/cập nhật {count} Court Cases (đã lọc các bản ghi không đạt chuẩn).")

def main():
    parser = argparse.ArgumentParser(description="Import legal data vào cơ sở dữ liệu.")
    parser.add_argument(
        "type", 
        choices=["case", "articles", "docs", "all"], 
        help="Loại dữ liệu cần import (case, articles, docs, hoặc all)"
    )
    parser.add_argument(
        "--no-clear", 
        action="store_false", 
        dest="clear", 
        help="Không xóa dữ liệu bảng trước khi import"
    )
    parser.set_defaults(clear=True)
    
    args = parser.parse_args()
    processed_dir = Path("data/processed")
    session = SessionLocal()
    
    try:
        # 1. Legal Docs
        if args.type in ["docs", "all"]:
            docs_dir = processed_dir / "legal_docs"
            if docs_dir.exists():
                import_legal_docs(session, docs_dir, clear=args.clear)
            
        # 2. Legal Articles
        if args.type in ["articles", "all"]:
            articles_dir = processed_dir / "legal_articles"
            if articles_dir.exists():
                import_legal_articles(session, articles_dir, clear=args.clear)
            
        # 3. Court Cases
        if args.type in ["case", "all"]:
            cases_dir = processed_dir / "court_cases"
            if cases_dir.exists():
                import_court_cases(session, cases_dir, clear=args.clear)
            
    except Exception as e:
        logger.error(f"❌ Lỗi trong quá trình import: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

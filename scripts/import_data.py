"""
Unified Data Import Script for VN-Legal-Bench-Dataset.
Imports LegalDocs, LegalArticles, and CourtCases into PostgreSQL with Upsert logic.
"""
import os
import json
import logging
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

def import_legal_docs(session: Session, data_dir: Path):
    logger.info("Importing Legal Documents...")
    files = list(data_dir.glob("*.json"))
    count = 0
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
                # Map JSON fields to DB columns
                stmt = insert(LegalDoc).values(
                    uid=item.get("uid") or item.get("doc_uid"),
                    doc_id=item.get("doc_id"),
                    title=item.get("title"),
                    doc_type=item.get("doc_type"),
                    issuing_body=item.get("issuing_body"),
                    issue_date=parse_date(item.get("issue_date") or item.get("Ngày ban hành")),
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
    logger.info(f"✓ Imported/Updated {count} Legal Documents.")

def import_legal_articles(session: Session, data_dir: Path):
    logger.info("Importing Legal Articles...")
    files = list(data_dir.glob("*.json"))
    count = 0
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
                # article_id in DB corresponds to article_uid in JSON for uniqueness
                stmt = insert(LegalArticle).values(
                    article_id=item.get("article_uid") or item.get("article_id"),
                    doc_uid=item.get("doc_uid"),
                    article_number=item.get("article_number"),
                    title=item.get("title"),
                    content=item.get("content"),
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
    logger.info(f"✓ Imported/Updated {count} Legal Articles.")

def import_court_cases(session: Session, data_dir: Path):
    logger.info("Importing Court Cases...")
    files = list(data_dir.glob("*.json"))
    count = 0
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
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
                        "summary": stmt.excluded.summary
                    }
                )
                session.execute(stmt)
                count += 1
    session.commit()
    logger.info(f"✓ Imported/Updated {count} Court Cases.")

def main():
    processed_dir = Path("data/processed")
    session = SessionLocal()
    
    try:
        # 1. Legal Docs
        docs_dir = processed_dir / "legal_docs"
        if docs_dir.exists():
            import_legal_docs(session, docs_dir)
            
        # 2. Legal Articles
        articles_dir = processed_dir / "legal_articles"
        if articles_dir.exists():
            import_legal_articles(session, articles_dir)
            
        # 3. Court Cases
        cases_dir = processed_dir / "court_cases"
        if cases_dir.exists():
            import_court_cases(session, cases_dir)
            
    except Exception as e:
        logger.error(f"Error during import: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()

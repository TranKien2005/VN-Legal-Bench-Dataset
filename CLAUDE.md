# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VN-Legal-Bench-Dataset is a Vietnamese legal benchmark dataset for evaluating LLMs on legal reasoning. It scrapes legal documents and court cases from Vietnamese government websites, stores them in PostgreSQL, and auto-generates benchmark questions using LLMs.

**Philosophy**: Follows [LegalBench](https://github.com/HazyResearch/legalbench) but uses more generalized task categories to reduce data requirements while maintaining diagnostic capability. Each task is independent and can serve as input to other tasks.

## Common Commands

### Environment Setup
```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
```

### Database
```bash
# Start PostgreSQL + pgAdmin via Docker
docker-compose up -d

# Initialize/create all tables (legal_docs, legal_articles, court_cases)
python scripts/init_db.py
```

### Scraping
```bash
# Court cases from luatvietnam.vn - topic mode with quota (default)
python scripts/scrape_luatvietnam_banan.py --quota 20

# Court cases - regular mode (keyword search)
python scripts/scrape_luatvietnam_banan.py --topic_mode --pages 5 --keyword "divorce"

# Legal documents from vanbanphapluat.co
python scripts/scrape_vbpl_luat.py
```

### Processing (Parse raw → DB)
```bash
python scripts/process_luatvietnam_banan.py  # Court cases
python scripts/process_vbpl_docs.py           # Legal documents
```

## Architecture

### Data Pipeline (5 layers)
```
scrapers/    → Collect from web (luatvietnam.vn, vanbanphapluat.co)
parsers/     → Parse into structured format
db/          → SQLAlchemy ORM (PostgreSQL)
scripts/     → CLI entry points for scraping/processing
generator/   → LLM-driven benchmark question generation (task_*.py)
data/        → Raw → Processed → Benchmark output
```

### Database Schema (3 main tables)

**legal_docs** — Legal normative documents (Luật, Nghị định, Thông tư...)
- UID format: `slugify(doc_id + title_prefix + issue_date)` — e.g., `24-1991-luat-luat-doanh-nghiep-1991-08-12`
- One-to-many with `legal_articles`

**legal_articles** — Individual articles within a legal doc
- Article ID: `[doc_uid]_D[article_number]` — e.g., `24-1991-..._D1`
- `is_amendment` flag indicates if article amends another legal text

**court_cases** — Court judgments
- UID format: `[CaseNumber]-[CourtAcronym]-[Date]`
- 4 parsed sections: `section_introduction` → `section_content` → `section_reasoning` → `section_decision`
- `legal_relation` field stores the legal category (e.g., "Ly hôn", "Tranh chấp đất đai")
- `decision_items` stored as JSON array

### Scrapers

- `luatvietnam_engine.py` — Court cases from luatvietnam.vn. Supports topic-based scraping with keyword quotas across 15 legal issue categories (configured in `config/search_topics.json`).
- `vbpl_engine.py` — Legal normative documents from vanbanphapluat.co.

### Parsers

- `case_parser.py` — Splits court case raw text into 4 sections using `CASE_SECTION_KEYWORDS` from constants.
- `legal_doc_parser.py` — Extracts articles using Sequential Skeleton Search algorithm (handles edge cases like old Sắc lệnh without article titles).
- `pdf_parser.py` — Uses PyMuPDF + Tesseract OCR for PDF text extraction.

### Generator (Benchmark Tasks)

The `generator/` folder contains task scripts that auto-generate benchmark questions using LLM clients:

| Script | Task | Source | Metric |
|--------|------|--------|--------|
| `task_1_1.py` | General Legal Issue Classification (15 labels) | court_cases | Accuracy |
| `task_1_2.py` | Core Issue Generation | court_cases | Token F1 / LLM-judge |
| `task_2_1.py` | Definition Recall | legal_articles | Token F1 / Exact Match |
| `task_2_2.py` | Article Recall | legal_articles | Token F1 / Exact Match |
| `task_2_3.py` | Legal Text Attribution (MCQ) | legal_articles + legal_docs | Accuracy |
| `task_2_4.py` | Legal Evolution | legal_articles (is_amendment=True) | Accuracy |
| `task_2_6.py` | Relevant Article Identification (MCQ) | court_cases.legal_bases | Accuracy |
| `task_3_1.py` | Legal Court Decision Prediction (MCQ) | court_cases + legal_articles | Accuracy |

**Output**: Each task generates JSON files to `data/benchmark/`.

**Task design principles**:
- Tasks use `section_content` (case facts) as input — `section_reasoning` is stripped to avoid giving away answers
- Multiple LLM calls per sample for complex tasks (3.1 uses ~4-6 calls)
- Agentic DB search (`db_search_agent.py`) used to link legal citations to database records
- Document distribution: 80% Luật, 18% Nghị định, 2% Special (per task plan)

### Configuration

- `config/settings.py` — Pydantic BaseSettings, loads from `.env`. DB credentials, API keys, paths.
- `config/constants.py` — 15 legal issue labels, DOC_TYPES, CASE_SECTION_KEYWORDS, ARGUMENT_ROLES.
- `config/search_topics.json` — 14 legal topics with keywords for quota-based scraping.

### Data Directories

- `data/raw/` — Raw JSON/HTML scraped from internet
- `data/processed/` — Parsed/structured data ready for DB
- `data/benchmark/` — Final benchmark JSON/CSV output

### Legal Issue Categories (15 labels)

Used for Issue Spotting tasks (1.1, 1.2):
1. Hôn nhân và Gia đình
2. Giao thông và Vận tải
3. Thuế, Phí và Lệ phí
4. Đất đai và Nhà ở
5. Lao động và Bảo hiểm xã hội
6. Kinh doanh và Đầu tư
7. Ngân hàng, Tín dụng và Bảo hiểm
8. Sở hữu trí tuệ
9. Môi trường và Tài nguyên
10. Trật tự, An toàn xã hội và Ma túy
11. Xâm phạm Quyền con người
12. Xâm phạm Quyền sở hữu tài sản
13. Hành chính và Quản lý nhà nước
14. Tư pháp và Tố tụng
15. Các vấn đề pháp lý khác

## Dependencies

- **DB**: PostgreSQL (or Docker), SQLAlchemy, alembic
- **Scraping**: playwright, beautifulsoup4, requests
- **PDF**: PyMuPDF, pdfplumber, pytesseract (requires system install + `vie.traineddata`)
- **LLM**: litellm (multi-provider), groq, google-generativeai
- **NLP**: underthesea (Vietnamese text processing)

## Notes

- Tesseract OCR must be installed system-wide with `vie.traineddata` in `tessdata` folder for PDF parsing.
- Chrome debug mode is used for some scraping tasks (`CHROME_DEBUG_PORT: 9222`).
- Python 3.11+ required (uses `str | None` union syntax).
- Court case scraping uses quota-based topic mode — each topic gets evenly distributed targets, with deficit carryover between keywords.
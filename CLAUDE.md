# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VN-Legal-Bench-Dataset is a Vietnamese legal benchmark dataset for evaluating LLMs on legal reasoning. It scrapes legal documents and court cases from Vietnamese legal websites, parses them into structured records, stores them in PostgreSQL, and generates benchmark questions with LLM calls.

The project follows LegalBench conceptually, but uses broader Vietnamese-law task categories so each generated task can be independent and can feed later tasks.

## Common Commands

### Environment Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

PDF parsing also requires a system Tesseract install with Vietnamese `vie.traineddata` available in the Tesseract `tessdata` folder. Verify with:
```bash
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

Configuration comes from `.env` via `config/settings.py`. Copy `.env.example` to `.env` if present, then set database credentials and any LLM API keys needed by generator scripts.

### Database
```bash
# Start PostgreSQL + pgAdmin
docker-compose up -d

# Create database tables
python scripts/init_db.py

# Drop and recreate all database tables
python scripts/init_db.py --reset
```

The Docker defaults are database `vn_legal_bench`, user `legal`, password `legal123`, PostgreSQL port `5432`, and pgAdmin port `8080`; `.env` can override them.

### Scraping Raw Data
```bash
# Court cases from luatvietnam.vn using topic quotas
python scripts/scrape_luatvietnam_banan.py --total_quota 300 --workers 3

# Legal normative documents from vanbanphapluat.co
python scripts/scrape_vbpl_luat.py --pages auto --start 1 --workers 5
python scripts/scrape_vbpl_nghi_dinh.py --pages auto --start 1 --workers 3
python scripts/scrape_vbpl_special.py

# Legal normative documents from luatvietnam.vn
python scripts/scrape_luatvietnam_luat.py --pages auto --start 1 --workers 3
python scripts/scrape_luatvietnam_nghi_dinh.py --pages auto --start 39 --workers 3
python scripts/scrape_luatvietnam_special.py
```

Court-case scraping uses `config/search_topics.json` for topic keywords. Some scraping flows use the Chrome debug settings in `config/settings.py` (`CHROME_PATH`, `CHROME_USER_DATA_DIR`, `CHROME_DEBUG_PORT`).

### Processing and Importing Data
```bash
# Parse raw files into data/processed
python scripts/process_luatvietnam_banan.py
python scripts/process_vbpl_docs.py
python scripts/process_vbpl_articles.py
python scripts/process_luatvietnam_docs.py
python scripts/process_luatvietnam_articles.py

# Import processed JSON into PostgreSQL; clears target tables by default
python scripts/import_data.py docs
python scripts/import_data.py articles
python scripts/import_data.py case
python scripts/import_data.py all

# Preserve existing DB rows while importing
python scripts/import_data.py all --no-clear
```

### Benchmark Generation
```bash
# Tasks with CLI limits
python generator/task_1_1.py --limit 20
python generator/task_1_1.py --all
python generator/task_1_2.py --limit 10
python generator/task_2_2.py --limit 10
python generator/task_2_6.py --limit 10
python generator/task_3_1.py --limit 5

# Tasks with fixed limits in __main__
python generator/task_2_1.py
python generator/task_2_3.py
python generator/task_2_4.py
```

Generated benchmark JSON files are written under `data/benchmark/`. Generator scripts usually require a populated database and configured LLM credentials.

### Tests and Checks
```bash
# pytest is installed as a development dependency, but this repo currently has no project test suite
pytest

# Run one test when tests are added
pytest path/to/test_file.py::test_name

# Quick LuatVietnam search smoke check
python scripts/diagnostic_search.py
```

There is no project-level build, lint, formatter, `pyproject.toml`, or pytest configuration at the repository root at the time this file was written.

## Architecture

### Data Pipeline
```
scrapers/  -> collect raw web data and downloaded documents
parsers/   -> normalize legal text and split it into structured fields
data/      -> raw, processed, and benchmark JSON/CSV artifacts
db/        -> SQLAlchemy ORM models, engine, and session setup
scripts/   -> command-line entry points for scraping, parsing, DB setup, and imports
generator/ -> LLM-driven benchmark task generation
```

### Storage Model

`db/models.py` defines three primary tables:

- `legal_docs`: legal normative documents such as Luật, Nghị định, Thông tư. The primary key `uid` is a composite slug based on document ID, title, and issue date to avoid historical ID collisions.
- `legal_articles`: individual articles linked to `legal_docs.uid` by `doc_uid`. Article IDs follow `[doc_uid]_D[article_number]`; `is_amendment` marks amendment articles.
- `court_cases`: court judgments with metadata, cited legal bases, decision items, raw text, and four parsed sections: `section_introduction`, `section_content`, `section_reasoning`, and `section_decision`.

### Scraping and Parsing

- `scrapers/vbpl_engine.py` collects legal normative documents from vanbanphapluat.co; type-specific scripts in `scripts/` pass document slugs such as `luat` and `nghi-dinh`.
- `scrapers/luatvietnam_engine.py` collects both court cases and legal normative documents from luatvietnam.vn. Court-case scraping uses topic quotas from `config/search_topics.json`; legal-document scripts pass LuatVietnam document type IDs for Luật/Bộ luật and Nghị định.
- `parsers/legal_doc_parser.py` extracts document metadata and articles from legal documents.
- `parsers/case_parser.py` splits court judgments into the four canonical sections used by benchmark tasks.
- `parsers/pdf_parser.py` uses PyMuPDF/pdfplumber/Tesseract OCR for PDF text extraction.

### Benchmark Generator

`generator/task_*.py` scripts query the database and write benchmark datasets. Tasks use case facts (`section_content`) as inputs and avoid leaking `section_reasoning` when the court reasoning would reveal the answer.

Task families:

- `task_1_1.py`: legal issue classification over the 15 configured issue categories.
- `task_1_2.py`: core issue generation.
- `task_2_1.py`, `task_2_2.py`: definition/article recall over legal articles.
- `task_2_3.py`: legal text attribution multiple choice.
- `task_2_4.py`: legal evolution from amendment articles.
- `task_2_6.py`: relevant article identification from court-case legal bases.
- `task_3_1.py`: court decision prediction; this is a multi-call pipeline and uses `generator/db_search_agent.py` to resolve cited legal bases against database records.

### Configuration and Constants

- `config/settings.py` loads `.env` with Pydantic settings for DB, API keys, data directories, and Chrome automation.
- `config/constants.py` contains legal issue labels, document types, parser section keywords, and related shared constants.
- `config/search_topics.json` controls court-case topic scraping quotas and keyword searches.

### Data Directories

- `data/raw/`: scraped source files and downloads.
- `data/processed/`: parsed JSON ready for inspection or DB import.
- `data/benchmark/`: generated benchmark outputs.

## Legal Issue Categories

Issue-spotting tasks use these 15 labels from `config/constants.py`:

1. Hôn nhân và Gia đình
2. Giao thông và Vận tải
3. Thuế, Phí và Lệ phí
4. Đất đai và Nhà ở
5. Lao động và Bảo hiểm xã hội
6. Kinh doanh, đầu tư, thương mại
7. Tài chính, vay nợ, tín dụng
8. Sở hữu trí tuệ
9. Môi trường và Tài nguyên
10. Trật tự, An toàn xã hội và Ma túy
11. Xâm phạm tính mạng, sức khỏe, danh dự, nhân phẩm
12. Xâm phạm sở hữu tài sản
13. Hành chính và Quản lý nhà nước
14. Tư pháp, Tố tụng và Thi hành án
15. Dân sự, Hợp đồng và Nghĩa vụ

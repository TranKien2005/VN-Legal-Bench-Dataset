# Cấu trúc Folder cho VN-Legal-Bench-Dataset

Dựa trên PROJECT_PLAN.md và tài liệu ý tưởng, đề xuất cấu trúc folder theo **pipeline xử lý dữ liệu** của dự án.

## Proposed Changes

### Cấu trúc tổng quan

```
VN-Legal-Bench-Dataset/
├── config/                     # Cấu hình chung
│   ├── __init__.py
│   ├── settings.py             # Load .env, DB connection, API keys
│   └── constants.py            # 15 legal issue labels, doc_types, etc.
│
├── db/                         # Database layer
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy models (legal_docs, legal_articles, cases)
│   ├── session.py              # DB session factory
│   └── migrations/             # Alembic migrations
│       ├── env.py
│       ├── alembic.ini
│       └── versions/
│
├── scrapers/                   # B2: Thu thập dữ liệu
│   ├── __init__.py
│   ├── base.py                 # Base scraper class
│   ├── court_cases.py          # congbobanan.toaan.gov.vn
│   └── legal_docs.py           # vanban.chinhphu.vn
│
├── parsers/                    # Trích xuất & parse dữ liệu thô
│   ├── __init__.py
│   ├── pdf_parser.py           # PyMuPDF/pdfplumber - trích xuất text từ PDF
│   ├── case_parser.py          # Tách bản án → intro/content/reasoning/decision
│   └── legal_doc_parser.py     # Tách VBQPPL → điều/khoản/điểm
│
├── generators/                 # B4-B5: Sinh câu hỏi benchmark
│   ├── __init__.py
│   ├── base.py                 # Base generator class
│   ├── issue_spotting.py       # Task 1.1, 1.2
│   ├── rule_recall.py          # Task 2.1 - 2.6
│   ├── rule_application.py     # Task 3.1
│   ├── interpretation.py       # Task 4.1 - 4.5
│   └── rhetorical.py           # Task 5.1 - 5.4
│
├── evaluation/                 # B6: Đánh giá LLM
│   ├── __init__.py
│   ├── metrics.py              # Accuracy, Token-F1, EM, LLM Judge
│   ├── runner.py               # Chạy evaluation trên nhiều LLM
│   └── prompts/                # Prompt templates cho evaluation
│       ├── zero_shot/
│       └── few_shot/
│
├── data/                       # Dữ liệu (gitignored, chỉ giữ trên local)
│   ├── raw/                    # Dữ liệu thô chưa xử lý
│   │   ├── court_cases/        # HTML/PDF bản án gốc
│   │   ├── legal_docs/         # PDF/HTML văn bản quy phạm
│   │   └── exam_papers/        # Đề thi (nếu có)
│   ├── processed/              # Dữ liệu đã xử lý, sẵn sàng import DB
│   └── benchmark/              # Output cuối cùng - bộ benchmark
│       ├── issue_spotting/
│       ├── rule_recall/
│       ├── rule_application/
│       ├── interpretation/
│       └── rhetorical/
│
├── notebooks/                  # Jupyter notebooks cho EDA & thử nghiệm
│
├── scripts/                    # Scripts chạy trực tiếp
│   ├── init_db.py              # Khởi tạo DB schema
│   ├── import_data.py          # Import dữ liệu vào DB
│   └── generate_benchmark.py   # Sinh toàn bộ benchmark
│
├── tests/                      # Unit tests
│   ├── test_parsers.py
│   ├── test_generators.py
│   └── test_metrics.py
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
├── PROJECT_PLAN.md
└── README.md
```

## Giải thích thiết kế

| Folder | Tương ứng kế hoạch | Lý do tách riêng |
|--------|-------------------|-------------------|
| `scrapers/` | B2 - Thu thập | Mỗi nguồn dữ liệu 1 scraper riêng |
| `parsers/` | B3 - Xây dựng CSDL | Tách text từ PDF, parse cấu trúc bản án/điều luật |
| `generators/` | B4, B5 - Sinh dữ liệu | Mỗi category 1 module, dùng chung base class |
| `evaluation/` | B6 - Đánh giá | Tách riêng metrics và runner |
| `data/raw/` | Dữ liệu thô | Gitignored, không push lên repo |
| `data/benchmark/` | Output cuối | Bộ benchmark hoàn chỉnh, chia theo category |
| `config/` | Cấu hình | Tập trung constants (15 nhãn, doc_types) |
| `db/` | CSDL | Models theo schema đã thiết kế (legal_docs, cases) |

## Một số quyết định thiết kế cần xác nhận

> [!IMPORTANT]
> 1. **`parsers/` tách riêng khỏi `scrapers/`**: Scraper chỉ lo tải về, parser lo trích xuất nội dung. Bạn có muốn gộp lại không?
> 2. **`data/benchmark/` chia theo 5 category**: Output benchmark chia theo category hay theo task (1.1, 1.2, 2.1,...)?
> 3. **Format output benchmark**: JSON, JSONL, hay CSV? Đề xuất dùng **JSONL** (mỗi dòng 1 sample) vì dễ đọc/stream.
> 4. **`notebooks/`**: Có cần thêm folder này cho việc thử nghiệm prompt và EDA không?

## Verification Plan

Sau khi tạo cấu trúc folder sẽ kiểm tra:
- Tất cả folder và `__init__.py` được tạo đúng
- [.gitignore](file:///d:/My%20Works/Coding/VN-Legal-Bench-Dataset/.gitignore) được cập nhật để ignore `data/raw/` và `data/processed/`
- Import thử các module để đảm bảo package structure hoạt động

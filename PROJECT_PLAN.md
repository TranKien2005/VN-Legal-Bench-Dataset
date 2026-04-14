# Kiến trúc & Cấu trúc Dự án (Architecture & Folder Structure)

Dự án **VN-Legal-Bench-Dataset** được thiết kế để tự động thu thập, bóc tách và phân phối dữ liệu hỗ trợ công tác đánh giá hệ thống LLM. Lược đồ luồng dữ liệu chính đi từ cào dữ liệu thô qua crawler, xử lý tại parser, lưu trữ có quan hệ vào Database và sau cùng là tạo ra bộ câu hỏi benchmark.

## 1. Cấu trúc thư mục (Directory Structure)

Dưới đây là các thư mục cốt lõi và vai trò của từng thành phần:

### `scrapers/`
- **Vai trò**: Chứa các "Engine" cào dữ liệu cốt lõi cho từng nguồn tin.
- **Công nghệ**: `playwright`, `bs4`.
- **Thành phần**:
  - `vbpl_engine.py`: Engine cho trang vanbanphapluat.co. Chuyên biệt cho văn bản quy phạm.
  - `luatvietnam_engine.py`: Engine cho trang luatvietnam.vn. Chuyên biệt cho bản án, tích hợp chế độ cào theo chủ đề (topic_mode) và xác thực tiêu đề nghiêm ngặt.

### `scripts/`
- **Vai trò**: Chứa các script chạy thực tế cho từng loại văn bản hoặc tác vụ cụ thể.
- **Thành phần**:
  - `scrape_vbpl_luat.py`: Script chuyên biệt để cào "Luật" từ VBPL.
  - `scrape_luatvietnam_banan.py`: Script điều khiển cào bản án. Hỗ trợ chế độ cào theo lĩnh vực pháp lý với hạn ngạch (quota) tự động.
  - `process_luatvietnam_banan.py`: Script bóc tách sâu bản án và lưu vào DB.

### `parsers/`
- **Vai trò**: Phân rã văn bản pháp lý đã thu thập được thành các luồng data có cấu trúc chi tiết, tách biệt.
- **Các thành phần cụ thể**:
  - `legal_doc_parser.py`: Phân rã Thông tư, Luật, Nghị định... thành từng Điều (Articles), tách riêng metadata (số hiệu văn bản, tên luật pháp cơ bản).
  - `case_parser.py`: Công cụ xử lý bản án phức tạp, tách bạch nội dung vụ án nguyên thủy thành 4 phần cốt lõi: Mở đầu -> Nội dung Vụ án -> Tòa Nhận định -> Quyết định cuối cùng.
  - `pdf_parser.py`: Dùng parser và công cụ OCR (Tesseract, PyMuPDF) trích xuất dữ liệu thô từ các file PDF tải về.

### `db/`
- **Vai trò**: Logic quản lý thao tác và thiết kế cơ sở dữ liệu (ORM).
- **Các thành phần cụ thể**:
  - `models.py`: Định nghĩa các cấu trúc bảng (Tables) thông qua SQLAlchemy:
    - Bảng `legal_docs` quản lý Metadata cốt lõi (Trạng thái hiệu lực `status`, loại văn bản `doc_type`, ngày có hiệu lực `effective_date`, `url`...) của văn bản phạm vi.
   ### 1. Standardized ID Format (Composite UID)
To handle historical law variations and ID collisions (e.g., older laws with same numbers in different years), we use a composite UID:
- **Format**: `slugify(doc_id + title_prefix + issue_date)`
- **Example**: `24-1991-luat-luat-doanh-nghiep-1991-08-12`
- **Article ID**: `[doc_uid]_D[article_number]` (e.g., `24-1991-luat-luat-doanh-nghiep-1991-08-12_D1`)

### 2. Legal Document Schema (legal_docs)
| Field | Type | Description |
| :--- | :--- | :--- |
| **uid** | String (PK) | Unique composite identifier |
| **doc_id** | String | Official document ID (e.g., 37/2024/QH15) |
| **title** | Text | Full title (extracted from text) |
| **doc_type** | String | Normalized type (Luật, Nghị định,...) |
| **issuing_body** | String | Issuing organization |
| **issue_date** | Date | Date of issuance |
| **effective_date** | Date | Date of effectivity |
| **status** | String | Effectiveness status |
| **url** | String | Source URL |
| **raw_text** | Text | Full content for extraction |

### 3. Court Case Schema (court_cases)
| Field | Type | Description |
| :--- | :--- | :--- |
| **uid** | String (PK) | Composite ID: `[CaseNumber]-[CourtAcronym]-[Date]` |
| **court_name** | Text | Full name of the issuing court |
| **issuance_date** | Date | Date the judgment was issued |
| **legal_relation** | String | Legal relationship (e.g., Ly hôn, Tranh chấp đất đai) |
| **legal_bases** | Text | Cited articles and laws (extracted) |
| **decision_items** | JSON | Array of specific court orders (1., 2., 3.) |
| **summary** | Text | Case summary from web source |
| **raw_text** | Text | Full text backup for audit |

### 3. Folder Structure
- `data/raw/legal_docs/`: Grouped page-level JSONs from scraper.
- `data/processed/legal_docs/`: Refined metadata with `uid` and extracted titles.
- `data/processed/legal_articles/`: Structured articles linked by `doc_uid`.
  - `raw/`: Các JSON/PDF/HTML nguyên thủy chưa qua xử lý từ Internet đổ vào.
  - `processed/`: Dữ liệu JSON đã được qua parse sơ bộ (như danh sách các document crawl được từ site).
  - `benchmark/`: Đích đến lưu trữ file JSON, CSV của bộ công cụ dataset benchmarking cuối cùng, sẵn sàng test LLM.

### `config/`
- **Vai trò**: Khởi tạo biến môi trường toàn cục cho dự án.
- **Các thành phần cụ thể**: 
  - `settings.py`: Khai báo Pydantic BaseSettings giúp load và quản lý class biến số từ `.env` khắt khe, an toàn (DB Port, Gemini Key, Groq Key, Absolute Dir Paths).
  - `constants.py`: Cấu hình danh mục hạng mục, mapping list chuẩn quy phạm chung để hệ thống gọi nhanh.

### `data/`
- **Vai trò**: Quản lý dữ liệu file local phục vụ làm việc offline hoặc review check luồng.
- **Các thành phần cụ thể**:
  - `raw/`: Các JSON/PDF/HTML nguyên thủy chưa qua xử lý từ Internet đổ vào.
  - `processed/`: Dữ liệu JSON đã được qua parse sơ bộ (như danh sách các document crawl được từ site).
  - `benchmark/`: Đích đến lưu trữ file JSON, CSV của bộ công cụ dataset benchmarking cuối cùng, sẵn sàng test LLM.

### `scripts/`
- **Vai trò**: Chứa các tệp chạy tiện ích độc lập (VD: Quản lý script cronjob định kỳ, Data Migrations như Alembic chạy version DB, hoặc công cụ tool chạy API sinh data Automation cho prompt LLM theo các hạng mục yêu cầu tự động).

---

## 2. Pipelined Architecture 

Mô tả sự phối hợp giữa 5 tầng thư mục trong hệ thống:

1. **Thu thập & Cấu trúc (Scraping & Structuring Layer - `scrapers/`)**: 
   Cào dữ liệu từ web, đồng thời sử dụng `parsers/` để chuẩn hóa metadata (ngày tháng, trạng thái, cơ quan ban hành) và tách Điều/Khoản ngay lập tức. Dữ liệu xuất ra dưới dạng JSON đã khớp với Schema của database.
2. **Xử lý chuyên sâu (Parsing Layer - `parsers/`)**:
   Cung cấp các công cụ chuẩn hóa (Normalization) và logic phân rã văn bản phức tạp (cho cả văn bản quy phạm và bản án). Đảm bảo tính nhất quán về kiểu dữ liệu (Data Types) cho toàn hệ thống.
3. **Lưu trữ CSDL (Storage Layer - `db/`)**:
   Tiếp nhận các Object đã được chuẩn hóa, lưu trữ thông qua SQLAlchemy ORM. Dữ liệu lúc này đã sạch và sẵn sàng cho việc truy vấn/sinh câu hỏi.
4. **Sinh lượng lớn Dataset (Generation Layer - `scripts/`)**: 
   Sử dụng các script CLI để điều khiển quá trình cào dữ liệu hoặc sinh câu hỏi benchmark từ Truth Data Pool trong database.
5. **Evaluation Output**: 
   Data đánh giá đẩy dưới dạng .json/.csv đổ về `data/benchmark/`.

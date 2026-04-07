# Kiến trúc & Cấu trúc Dự án (Architecture & Folder Structure)

Dự án **VN-Legal-Bench-Dataset** được thiết kế để tự động thu thập, bóc tách và phân phối dữ liệu hỗ trợ công tác đánh giá hệ thống LLM. Lược đồ luồng dữ liệu chính đi từ cào dữ liệu thô qua crawler, xử lý tại parser, lưu trữ có quan hệ vào Database và sau cùng là tạo ra bộ câu hỏi benchmark.

## 1. Cấu trúc thư mục (Directory Structure)

Dưới đây là các thư mục cốt lõi và vai trò của từng thành phần:

### `scrapers/`
- **Vai trò**: Cào dữ liệu (Crawling/Scraping) từ các trang web như vanbanphapluat, congbobanan, v.v.
- **Công nghệ**: `playwright`, `requests`, `BeautifulSoup`.
- **Ví dụ luồng**: Khởi chạy một CDP Crawler với Chrome debugging thông qua thư viện Playwright (`vanbanphapluat_cdp_scraper.py`) để vượt qua các bộ lọc như Cloudflare, xuất dữ liệu thô (raw text, metadata) và định dạng xuất thành JSON đưa vào thư mục tạm `data/processed/`.

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
    - Bảng `legal_articles` chứa nội dung từng Điều luật chi tiết tách từ `legal_docs`.
    - Bảng `court_cases` cho kho Bản án phục vụ suy luận pháp lý.
  - `session.py`: Quản lý các cấu hình kết nối trực tiếp đến PostgreSQL engine.

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

1. **Thu thập (Scraping Layer - `scrapers/`)**: 
   Cào file, bản án, kho luật. Sinh ra định dạng RAW và chuyển cho Processed Layer.
2. **Tiền xử lý (Parsing Layer - `parsers/`)**:
   Tổ chức đọc file từ ổ tĩnh, Cleaning (làm sạch), sử dụng Regex hoặc thư viện xử lý chữ để trích xuất từng entity nhỏ cấu trúc lại thành Pydantic object hoặc Dicts ổn định.
3. **Lưu trữ CSDL (Storage Layer - `db/`)**:
   Tiếp nhận các Object hoàn hảo từ Parsing đẩy qua SQLAlchemy ORM đi thẳng vào Server PostgreSQL (Đóng vai trò Truth Data Pool sạch và thống nhất).
4. **Sinh lượng lớn Dataset (Generation Layer - `scripts/` + `parsers/`)**: 
   Scripts tự động nhặt mẫu (Case / Article) từ database đưa qua đường dẫn API (Gemini/LiteLLM), nhận cấu trúc hỏi-đáp MCQ/Gen Text chia 5 category của benchmark (Chi tiết phương pháp và dataset plan xem ngay bên `Ý tưởng và kế hoạch xây dựng dữ liệu .txt`).
5. **Evaluation Output**: 
   Data đánh giá đẩy dưới dạng .json/.csv đổ về `data/benchmark/`.

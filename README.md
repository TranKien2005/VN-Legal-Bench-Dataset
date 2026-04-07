# VN-Legal-Bench-Dataset

Bộ dữ liệu đánh giá khả năng suy luận pháp lý Việt Nam của mô hình Ngôn ngữ Lớn (LLM), hoạt động với ý tưởng tương tự [LegalBench](https://github.com/HazyResearch/legalbench) nhưng với cấu trúc cấp task tổng quát, tiết kiệm và tối ưu hiệu quả hơn cho đặc thù pháp lý Việt Nam.

Dự án thực hiện tự động lấy dữ liệu từ các Cổng thông tin (bản án, văn bản QPPL), phân tách/thống kê vào Database, và tự động sinh câu hỏi đánh giá theo 5 hạng mục pháp lý (Chi tiết nội dung này nằm trong tài liệu text: `Ý tưởng và kế hoạch xây dựng dữ liệu .txt`).

## ⚙️ Hướng dẫn Setup

### 1. Cài đặt Source và Requirements
Clone repository và tạo một virtual environment tiêu chuẩn:
```bash
git clone <repo-url>
cd VN-Legal-Bench-Dataset
python -m venv venv
venv\Scripts\activate  # Lệnh riêng cho Windows
pip install -r requirements.txt
```

### 2. Tiện ích Tesseract OCR (Hỗ trợ parse PDF)
- Tải file Setup cài đặt cho Windows từ nhánh: `tesseract-ocr-w64-setup-5.3.4.20240524.exe` trên Github ([tesseract wiki](https://github.com/UB-Mannheim/tesseract/wiki)).
- Cài đặt và đảm bảo đường dẫn `tesseract.exe` đã được cài vào PATH Windows Environment.
- Tải pack ngôn ngữ `vie.traineddata` (Tiếng Việt) và copy ném vào folder `tessdata`.
- Check cài đặt thành công:
```bash
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

### 3. Cấu hình Data & Variables
- Copy file `.env.example` sửa tên thành `.env`. Điền API Keys của các model mong muốn sử dụng (Gemini, Groq, OpenAI,...).
- Đảm bảo bạn có sẵn Hệ thống PostgreSQL hoặc Docker ở local và khai báo đủ thông số DB (Port, User, PW) trên `.env`.

---

## 📂 Tổ chức mã nguồn
- Hệ thống chia lớp kiến trúc rõ ràng: Cào (`scrapers/`) -> Parse cấu trúc (`parsers/`) -> Core CSDL ORM (`db/`) -> Data Pipeline Scripts (`scripts/`).
- Mời tham khảo kĩ chi tiết vai trò của các luồng code tại [PROJECT_PLAN.md](./PROJECT_PLAN.md).
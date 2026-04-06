## VN-Legal-Bench-Dataset

### Cài đặt

1. Clone repository và tạo virtual environment:
```bash
git clone <repo-url>
cd VN-Legal-Bench-Dataset
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. Cài đặt Tesseract OCR (cho Windows):
   - Tải về từ: https://github.com/UB-Mannheim/tesseract/wiki
   - Chọn version phù hợp với hệ thống (tesseract-ocr-w64-setup-5.3.4.20240524.exe)
   - Cài đặt và đảm bảo `tesseract.exe` có trong PATH
   - Tải language pack tiếng Việt: https://github.com/tesseract-ocr/tessdata
   - Copy `vie.traineddata` vào thư mục tessdata của Tesseract

3. Kiểm tra cài đặt:
```bash
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

### Sử dụng
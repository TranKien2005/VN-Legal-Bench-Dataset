"""
Trích xuất text từ file PDF hoặc TXT.

Hỗ trợ 2 chế độ:
  1. Text-based PDF: dùng PyMuPDF extract trực tiếp (nhanh, chính xác)
  2. Scanned/Image PDF: dùng Tesseract OCR (nhanh hơn, khuyến nghị)
  3. TXT files: đọc trực tiếp

Tự động phát hiện: nếu text layer quá ít so với số trang thì chuyển sang OCR.

Cấu hình OCR:
  - Tesseract language: TESSDATA_PREFIX env hoặc mặc định "vie"
"""
import sys
from functools import lru_cache
from pathlib import Path
import fitz  # PyMuPDF
import os
import pytesseract
from pdf2image import convert_from_path

# Đảm bảo UTF-8 encoding cho tiếng Việt
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Ngưỡng: nếu trung bình mỗi trang < 50 ký tự -> coi là scanned PDF
MIN_CHARS_PER_PAGE = 50
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "vie").strip() or "vie"


def _is_scanned_pdf(doc: fitz.Document) -> bool:
    """Kiểm tra PDF có phải dạng scan (ảnh) không."""
    total_text_len = 0
    pages_to_check = min(len(doc), 5)  # Chỉ check 5 trang đầu

    for i in range(pages_to_check):
        text = doc[i].get_text("text")
        total_text_len += len(text.strip())

    avg_chars = total_text_len / pages_to_check if pages_to_check > 0 else 0
    return avg_chars < MIN_CHARS_PER_PAGE


def _extract_text_native(doc: fitz.Document) -> str:
    """Trích xuất text trực tiếp từ text layer (nhanh)."""
    pages_text = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages_text.append(text)
    return "\n".join(pages_text)


@lru_cache(maxsize=1)
def _get_tesseract_config():
    """Khởi tạo Tesseract config."""
    try:
        import pytesseract
        
        # Tự động tìm đường dẫn Tesseract trên Windows
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        
        tesseract_path = None
        for path in possible_paths:
            if os.path.exists(path):
                tesseract_path = path
                break
        
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        else:
            # Nếu không tìm thấy, thử dùng PATH
            pass
        
        # Kiểm tra Tesseract đã cài đặt
        pytesseract.get_tesseract_version()
    except Exception as e:
        raise RuntimeError(
            "Tesseract OCR chưa sẵn sàng. Hãy cài đặt Tesseract và đảm bảo pytesseract."
        ) from e
    
    return {
        'lang': TESSERACT_LANG,
        'config': '--psm 6'  # Uniform block of text
    }


def _extract_text_tesseract(pdf_path: Path) -> list[str]:
    """Trích xuất text theo từng trang bằng Tesseract OCR."""
    config = _get_tesseract_config()
    
    # Đường dẫn poppler từ conda
    poppler_path = os.path.join(os.environ.get('USERPROFILE', ''), 'miniconda3', 'Library', 'bin')
    
    # Chuyển PDF thành images
    images = convert_from_path(str(pdf_path), poppler_path=poppler_path)
    
    pages_text = []
    for idx, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(image, lang=config['lang'], config=config['config'])
        pages_text.append(text.strip())
        
        if idx % 10 == 0:
            print(f"  Tesseract OCR: {idx} trang...")
    
    return pages_text


def _extract_text_ocr(
    pdf_path: Path,
    lang: str = "vie",
) -> list[str]:
    """Trích xuất text bằng Tesseract OCR."""
    print(f"  -> Dang dung Tesseract OCR (lang={TESSERACT_LANG})...")
    try:
        pages = _extract_text_tesseract(pdf_path)
        if any(page.strip() for page in pages):
            return pages
        raise RuntimeError("Tesseract OCR không trả về text nào.")
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR thất bại: {e}") from e


def extract_text_from_txt(txt_path: str | Path) -> str:
    """
    Trích xuất text trực tiếp từ file TXT.
    
    Args:
        txt_path: Đường dẫn đến file TXT.
        
    Returns:
        Nội dung text của file.
    """
    txt_path = Path(txt_path)
    if not txt_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {txt_path}")
    
    if txt_path.suffix.lower() != '.txt':
        raise ValueError(f"File phải có đuôi .txt: {txt_path}")
    
    with open(txt_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_text_from_pdf(
    pdf_path: str | Path,
    force_ocr: bool = False,
    lang: str = "vie",
) -> str:
    """
    Trích xuất toàn bộ text từ file PDF.

    Tự động phát hiện PDF scan và dùng Tesseract OCR nếu cần.

    Args:
        pdf_path: Đường dẫn đến file PDF.
        force_ocr: Bắt buộc dùng OCR (bỏ qua text layer).
        lang: Ngôn ngữ cho OCR.

    Returns:
        Toàn bộ text trong PDF.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {pdf_path}")

    doc = fitz.open(str(pdf_path))

    try:
        if force_ocr or _is_scanned_pdf(doc):
            print(f"  -> PDF scan detected, dùng Tesseract OCR...")
            pages = _extract_text_ocr(pdf_path, lang=lang)
            return "\n\n".join(page for page in pages if page.strip())
        return _extract_text_native(doc)
    finally:
        doc.close()


def extract_text_from_file(
    file_path: str | Path,
    force_ocr: bool = False,
    lang: str = "vie",
) -> str:
    """
    Trích xuất text từ file PDF hoặc TXT.
    
    Args:
        file_path: Đường dẫn đến file PDF hoặc TXT.
        force_ocr: Bắt buộc dùng OCR cho PDF (bỏ qua text layer).
        lang: Ngôn ngữ cho OCR.
        
    Returns:
        Toàn bộ text trong file.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
    
    suffix = file_path.suffix.lower()
    if suffix == '.txt':
        return extract_text_from_txt(file_path)
    elif suffix == '.pdf':
        return extract_text_from_pdf(file_path, force_ocr=force_ocr, lang=lang)
    else:
        raise ValueError(f"Không hỗ trợ định dạng file: {suffix}. Chỉ hỗ trợ .pdf và .txt")


def extract_text_per_page_from_txt(txt_path: str | Path) -> list[str]:
    """
    Trích xuất text theo từng "trang" từ file TXT.
    Giả sử mỗi trang được phân cách bởi 2 dòng trống.
    
    Args:
        txt_path: Đường dẫn đến file TXT.
        
    Returns:
        List các string, mỗi phần tử là text của 1 "trang".
    """
    content = extract_text_from_txt(txt_path)
    # Chia theo 2 dòng trống
    pages = content.split('\n\n\n')
    return [page.strip() for page in pages if page.strip()]


def extract_text_per_page_pdf(
    pdf_path: str | Path,
    force_ocr: bool = False,
    lang: str = "vie",
) -> list[str]:
    """
    Trích xuất text theo từng trang từ file PDF.

    Args:
        pdf_path: Đường dẫn đến file PDF.
        force_ocr: Bắt buộc dùng OCR.
        lang: Ngôn ngữ cho OCR.

    Returns:
        List các string, mỗi phần tử là text của 1 trang.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {pdf_path}")

    doc = fitz.open(str(pdf_path))

    try:
        use_ocr = force_ocr or _is_scanned_pdf(doc)
        if use_ocr:
            return _extract_text_ocr(pdf_path, lang=lang)

        return [page.get_text("text") for page in doc]
    finally:
        doc.close()


def extract_text_per_page(
    file_path: str | Path,
    force_ocr: bool = False,
    lang: str = "vie",
) -> list[str]:
    """
    Trích xuất text theo từng trang từ file PDF hoặc TXT.
    
    Args:
        file_path: Đường dẫn đến file PDF hoặc TXT.
        force_ocr: Bắt buộc dùng OCR cho PDF.
        lang: Ngôn ngữ cho OCR.
        
    Returns:
        List các string, mỗi phần tử là text của 1 trang.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    if suffix == '.txt':
        return extract_text_per_page_from_txt(file_path)
    elif suffix == '.pdf':
        return extract_text_per_page_pdf(file_path, force_ocr=force_ocr, lang=lang)
    else:
        raise ValueError(f"Không hỗ trợ định dạng file: {suffix}. Chỉ hỗ trợ .pdf và .txt")

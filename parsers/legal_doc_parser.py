import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date

def slugify(text: str) -> str:
    """Tạo slug chuẩn cho UID: Xử lý đ/Đ và loại bỏ ký tự đặc biệt."""
    if not text: return "unknown"
    text = text.replace('đ', 'd').replace('Đ', 'D')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[-\s]+', '-', text)
    return text

@dataclass
class ParsedArticle:
    article_id: str      # Định dạng cũ: 1/35/2024/QH15
    doc_id: str          # Số hiệu: 35/2024/QH15
    doc_uid: str         # UID cha: luat-35-2024-qh15-...
    article_uid: str     # UID duy nhất: dieu-1-luat-35-2024-qh15-...
    article_number: str
    title: str | None
    content: str
    is_amendment: bool = False

@dataclass
class ParsedLegalDoc:
    uid: str = ""        # [Type]-[Number]-[SlugTitle]-[Date]
    doc_id: str = ""     # Số hiệu
    title: str = ""      # Ưu tiên lấy từ Caps Block nội dung
    doc_type: str | None = None
    issuing_body: str | None = None
    legal_field: str | None = None
    is_amendment: bool = False
    issue_date: date | None = None
    effective_date: date | None = None
    status: str | None = None
    url: str | None = None
    raw_text: str | None = None
    articles: list[ParsedArticle] = field(default_factory=list)

def is_valid_doc_content(title_web: str, doc_id: str) -> bool:
    """Kiểm tra văn bản hợp lệ (không phải dự thảo, có số hiệu)."""
    title = (title_web or "").lower()
    if any(kw in title for kw in ["dự thảo", "dự kiến", "góp ý"]):
        return False
    if not doc_id or len(doc_id) < 3 or doc_id.lower() in ["đang cập nhật", "chưa rõ"]:
        return False
    return True

def extract_title_from_text(text: str) -> str | None:
    """Trích xuất tiêu đề bằng cơ chế khối VIẾT HOA liên tục (Caps Block)."""
    doc_types = ["LUẬT", "NGHỊ ĐỊNH", "NGHỊ QUYẾT", "THÔNG TƯ", "QUYẾT ĐỊNH", "HIẾN PHÁP", "LỆNH", "SẮC LỆNH"]
    lines = text.split('\n')
    start_idx = -1
    for i, line in enumerate(lines[:50]): # Tìm trong 50 dòng đầu
        line_clean = line.strip()
        if any(line_clean.startswith(dt) for dt in doc_types):
            start_idx = i
            break
    if start_idx == -1: return None
    
    title_parts = []
    for i in range(start_idx, len(lines)):
        line_clean = lines[i].strip()
        if not line_clean: continue
        # Dừng nếu gặp "Căn cứ", Chữ thường, hoặc Danh sách
        if re.search(r"^\s*Căn\s+cứ\b", line_clean, re.IGNORECASE): break
        if any(c.islower() for c in line_clean): break
        title_parts.append(line_clean)
        
    if not title_parts: return None
    return re.sub(r"\s+", " ", " ".join(title_parts)).strip()

def split_articles(text: str, doc_id: str, doc_uid: str, is_amendment: bool = False) -> list[ParsedArticle]:
    """
    THUẬT TOÁN: Sequential Skeleton Search & Strict Title Split
    """
    articles = []
    # Tìm tất cả "Điều X"
    pattern = re.compile(r'(?:^|\n)Điều\s+(\d+[a-z]?)\.?[\t ]*', re.IGNORECASE)
    matches = list(pattern.finditer(text))
    
    # 1. Cơ chế lọc trích dẫn: Loại bỏ các Điều nằm trong dấu ngoặc kép "..."
    # (Tạm thời xử lý bằng cách kiểm tra context phía trước)
    valid_matches = []
    for m in matches:
        pre_context = text[max(0, m.start()-10):m.start()]
        if '“' in pre_context or '"' in pre_context: continue # Bỏ qua điều trích dẫn
        valid_matches.append(m)

    # 2. Cơ chế Điều liên tục (Sequential Skeleton):
    # Một văn bản chính thốn phải bắt đầu từ Điều 1 và tăng dần.
    final_matches = []
    next_expected = 1
    found_start = False
    
    for m in valid_matches:
        num_str = m.group(1)
        try: num = int(re.sub(r'[a-z]', '', num_str))
        except: continue
        
        if not found_start:
            if num == 1:
                found_start = True
                next_expected = 2
                final_matches.append(m)
        else:
            # Chấp nhận nếu đúng số hiệu tiếp theo hoặc một bước nhảy nhỏ hợp lý
            if num == next_expected:
                final_matches.append(m)
                next_expected += 1
            elif num < next_expected: # Điều cũ xuất hiện lại -> cite
                continue
            elif num > next_expected + 5: # Nhảy quá xa -> nghi ngờ cite
                continue
            else: # Nhảy số nhỏ (ví dụ lỡ mất 1 điều) -> vẫn lấy
                final_matches.append(m)
                next_expected = num + 1

    # 3. Bóc tách chi tiết với Logic "Chữ hoa = Nội dung" (Strict Title Split)
    for i in range(len(final_matches)):
        m = final_matches[i]
        art_num = m.group(1)
        start_pos = m.end()
        end_pos = final_matches[i+1].start() if i + 1 < len(final_matches) else len(text)
        
        segment = text[start_pos:end_pos].strip('\r')
        if not segment: continue
        
        # --- SMART SPLIT & MULTI-LINE TITLE ---
        lines = segment.split('\n')
        art_title_parts = []
        art_content_parts = []
        found_content = False
        
        # Step 1: Phân tích dòng đầu tiên
        first_line = lines[0].strip()
        if not first_line: # Nếu Điều X xuống dòng ngay lập tức
             found_content = True
        else:
            # Smart Split: Dấu chấm + Chữ hoa
            dot_match = re.search(r'\.\s+([A-ZÀ-Ỹ])', first_line)
            if dot_match:
                art_title_parts.append(first_line[:dot_match.start() + 1])
                art_content_parts.append(first_line[dot_match.start() + 1:].strip())
                found_content = True
            else:
                art_title_parts.append(first_line)
        
        # Step 2 & 3: Gom tiếp tiêu đề hoặc dừng nếu gặp Chữ hoa/Danh sách
        if not found_content:
            for i, line in enumerate(lines[1:]):
                l_strip = line.strip()
                if not l_strip: continue
                
                # Điểm dừng: Viết hoa, số hiệu khoản (1., 2.) hoặc điểm (a, b)
                if l_strip[0].isupper() or re.match(r'^(\d+|[a-z]|chương|mục)[\.\),]', l_strip, re.IGNORECASE):
                    found_content = True
                    # Khi đã tìm thấy dòng bắt đầu nội dung, gom toàn bộ phần còn lại
                    art_content_parts.extend(lines[1+i:])
                    break
                else:
                    art_title_parts.append(l_strip)
        else:
            art_content_parts.extend(lines[1:])
            
        art_title = " ".join(art_title_parts).strip()
        art_content = "\n".join(art_content_parts).strip()
        
        # Step 4: Fail-safe (> 200 chars or ellipses)
        if art_title and (len(art_title) > 200 or '...' in art_title):
            art_content = (art_title + "\n" + art_content).strip()
            art_title = None

        articles.append(ParsedArticle(
            article_id=f"{art_num}/{doc_id}",
            doc_id=doc_id,
            doc_uid=doc_uid,
            article_uid=f"{slugify(f'dieu {art_num}')}-{doc_uid}",
            article_number=art_num,
            title=art_title,
            content=art_content,
            is_amendment=is_amendment
        ))
        
    return articles

def infer_issuing_body(doc_id: str) -> str | None:
    if not doc_id: return None
    doc_id = doc_id.upper()
    if re.search(r"/(QH\d*)$", doc_id) or "/NQ-QH" in doc_id: return "Quốc hội"
    if re.search(r"/(TVQH\d*|UBTVQH\d*)$", doc_id): return "Ủy ban Thường vụ Quốc hội"
    if "/NĐ-CP" in doc_id or "/NQ-CP" in doc_id: return "Chính phủ"
    if "/QĐ-TTG" in doc_id or "/CT-TTG" in doc_id: return "Thủ tướng Chính phủ"
    if "/L-CTN" in doc_id or "/QĐ-CTN" in doc_id or "/SL" in doc_id: return "Chủ tịch nước"
    return None

def parse_vn_date(date_str: str | None) -> date | None:
    if not date_str or not isinstance(date_str, str): return None
    patterns = [r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})']
    for p in patterns:
        m = re.search(p, date_str.strip())
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4: return date(int(g[0]), int(g[1]), int(g[2]))
                else: return date(int(g[2]), int(g[1]), int(g[0]))
            except: continue
    return None

def normalize_status(status_raw: str | None) -> str:
    if not status_raw: return "Không xác định"
    s = re.split(r'\d', status_raw.lower())[0].strip()
    if any(kw in s for kw in ["hết hiệu lực một phần", "sửa đổi", "bổ sung"]): return "Hết hiệu lực một phần"
    if any(kw in s for kw in ["hết hiệu lực", "bị hủy bỏ", "bị bãi bỏ"]): return "Hết hiệu lực"
    if any(kw in s for kw in ["còn hiệu lực", "đang áp dụng"]): return "Còn hiệu lực"
    return "Không xác định"

def parse_legal_doc(text: str, **kwargs) -> ParsedLegalDoc:
    """Hàm trung tâm: Ưu tiên bóc tách CAPS Title và tạo UID chuẩn."""
    doc_id = kwargs.get("doc_id", "").strip()
    doc_type = kwargs.get("doc_type", "Văn bản")
    title_web = kwargs.get("title_web", "")
    
    # 1. Ưu tiên bóc tách tiêu đề IN HOA từ nội dung
    extracted_title = extract_title_from_text(text)
    final_title = extracted_title or title_web or f"{doc_type} {doc_id}"
    
    doc = ParsedLegalDoc(
        doc_id=doc_id,
        title=final_title.strip(),
        doc_type=doc_type,
        issuing_body=kwargs.get("issuing_body") or infer_issuing_body(doc_id),
        legal_field=kwargs.get("field"),
        issue_date=parse_vn_date(kwargs.get("issue_date_str")),
        effective_date=parse_vn_date(kwargs.get("effective_date_str")),
        url=kwargs.get("url"),
        raw_text=text
    )
    
    # 2. Tạo UID Duy nhất theo công thức đã thống nhất
    issue_date_str = str(doc.issue_date) if doc.issue_date else "unknown"
    uid_parts = [slugify(doc_type), slugify(doc_id), slugify(title_web or doc.title), slugify(issue_date_str)]
    doc.uid = "-".join(filter(None, uid_parts))
    
    doc.status = normalize_status(kwargs.get("status_str"))
    if any(kw in doc.title.lower() or kw in title_web.lower() for kw in ["sửa đổi", "bổ sung"]):
        doc.is_amendment = True
        
    return doc

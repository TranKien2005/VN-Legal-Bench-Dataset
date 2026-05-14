import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any

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
    signer: str | None = None
    summary: str | None = None
    download_links: list[dict[str, Any]] | None = None
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

def _is_caps_title_line(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    upper_count = sum(1 for c in letters if c.isupper())
    return upper_count / len(letters) >= 0.8


def clean_luatvietnam_raw_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[​‌‍﻿­]", "", text)
    noise_lines = {"đang theo dõi", "bổ sung"}
    lines = []
    for line in text.splitlines():
        clean_line = line.strip()
        if clean_line.lower() in noise_lines:
            continue
        if "data-href=" in clean_line or "docitem-view-change-content" in clean_line:
            continue
        lines.append(line)
    return "\n".join(lines)


def extract_title_from_text(text: str) -> str | None:
    """Trích xuất tiêu đề từ dòng loại văn bản và các dòng mô tả ngay sau đó."""
    text = unicodedata.normalize('NFC', text)
    doc_types = ["BỘ LUẬT", "LUẬT", "NGHỊ ĐỊNH", "NGHỊ QUYẾT", "THÔNG TƯ", "QUYẾT ĐỊNH", "HIẾN PHÁP", "LỆNH", "SẮC LỆNH"]
    lines = text.split('\n')
    start_idx = -1
    for i, line in enumerate(lines[:50]):
        line_clean = line.strip()
        if line_clean == "LUẬT" and i >= 2:
            prev_tokens = [lines[i - 2].strip().upper(), lines[i - 1].strip().upper()]
            if prev_tokens == ["B", "Ộ"]:
                lines[i] = "BỘ LUẬT"
                start_idx = i
                break
        if any(line_clean.startswith(dt) for dt in doc_types):
            start_idx = i
            break
    if start_idx == -1:
        return None

    next_title_line = None
    for line in lines[start_idx + 1:start_idx + 6]:
        line_clean = line.strip()
        if line_clean:
            next_title_line = line_clean
            break
    caps_block_mode = bool(next_title_line and _is_caps_title_line(next_title_line))

    title_parts = []
    for line in lines[start_idx:start_idx + 12]:
        line_clean = line.strip()
        if not line_clean:
            continue
        if re.search(r"^\s*Căn\s+cứ\b", line_clean, re.IGNORECASE):
            break
        if re.match(r"^(Chương|Mục|Điều)\s+", line_clean, re.IGNORECASE):
            break
        if re.search(r"^(Nơi nhận|TM\.|KT\.|THỦ TƯỚNG|BỘ TRƯỞNG|CHỦ TỊCH)\b", line_clean, re.IGNORECASE):
            break
        if caps_block_mode and title_parts and any(c.islower() for c in line_clean):
            break
        title_parts.append(line_clean)

    if not title_parts:
        return None
    return re.sub(r"\s+", " ", " ".join(title_parts)).strip()

def split_articles(text: str, doc_id: str, doc_uid: str, is_amendment: bool = False) -> list[ParsedArticle]:
    """
    THUẬT TOÁN: Sequential Skeleton Search & Strict Title Split
    """
    text = unicodedata.normalize('NFC', text)
    articles = []
    pattern = re.compile(r'(?m)^[\t ]*Điều\s+(\d+[a-z]?)\b(?:\s*\.)?[\t ]*([^\n]*)$', re.IGNORECASE)
    matches = list(pattern.finditer(text))

    def segment_word_count(start: int, end: int) -> int:
        return len(re.findall(r"\w+", clean_luatvietnam_raw_text(text[start:end]), re.UNICODE))

    def is_article_heading(match) -> bool:
        heading_tail = match.group(2).strip()
        if not heading_tail:
            following_lines = text[match.end():].splitlines()
            next_line = next((line.strip() for line in following_lines if line.strip()), "")
            if re.match(r"^(và|hoặc|của|theo|tại|khoản|điểm)\b", next_line, re.IGNORECASE):
                return False
            return True
        if "." in heading_tail:
            return False
        return True

    # 1. Cơ chế lọc trích dẫn và ranh giới: chỉ nhận dòng tiêu đề Điều hợp lệ.
    valid_matches = []
    for m in matches:
        pre_context = text[max(0, m.start()-10):m.start()]
        if '“' in pre_context or '"' in pre_context:
            continue
        if not is_article_heading(m):
            continue
        valid_matches.append(m)

    # 2. Cơ chế Điều liên tục (Sequential Skeleton):
    # Một văn bản chính thống phải bắt đầu từ Điều 1 và tăng dần.
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
            # Chỉ chấp nhận đúng số hiệu tiếp theo; mọi số khác được xem là trích dẫn/nhiễu
            if num == next_expected:
                final_matches.append(m)
                next_expected += 1
            else:
                continue

    # 3. Nếu ranh giới không có tên Điều và tạo ra đoạn quá ngắn, coi đó là nhiễu.
    compacted_matches = []
    for i, m in enumerate(final_matches):
        end_pos = final_matches[i+1].start() if i + 1 < len(final_matches) else len(text)
        heading_tail = m.group(2).strip()
        if compacted_matches and not heading_tail and segment_word_count(m.end(), end_pos) < 15:
            continue
        compacted_matches.append(m)
    final_matches = compacted_matches

    # 3. Bóc tách chi tiết với Logic "Chữ hoa = Nội dung" (Strict Title Split)
    for i in range(len(final_matches)):
        m = final_matches[i]
        art_num = m.group(1)
        start_pos = m.end()
        end_pos = final_matches[i+1].start() if i + 1 < len(final_matches) else len(text)
        
        segment = clean_luatvietnam_raw_text(text[start_pos:end_pos]).strip('\r')
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
                if first_line.endswith('.'):
                    art_content_parts.append(first_line)
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

        if not art_content and art_title:
            junk_title = re.fullmatch(r"[,;:.\-–—\s]+", art_title) or re.match(
                r"^(của\s+(Luật|Nghị định|Thông tư|Nghị quyết)\s+này|và|hoặc|Sửa đổi,\s*bổ sung|Bổ sung\s+Điều)",
                art_title,
                re.IGNORECASE
            )
            if junk_title:
                continue
            art_content = art_title
            art_title = None

        # Step 4: Fail-safe (> 200 chars or ellipses)
        if art_title and (len(art_title) > 200 or '...' in art_title):
            art_content = (art_title + "\n" + art_content).strip()
            art_title = None

        if not art_content.strip():
            continue

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
    cleaned = date_str.strip().lower()
    if not cleaned or cleaned in {"đã biết", "đang cập nhật", "chưa rõ"}: return None
    patterns = [r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})']
    for p in patterns:
        m = re.search(p, cleaned)
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4: return date(int(g[0]), int(g[1]), int(g[2]))
                else: return date(int(g[2]), int(g[1]), int(g[0]))
            except: continue
    m = re.search(r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})', cleaned)
    if m:
        try: return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except: return None
    return None


def extract_effective_date_from_text(issue_date: date | None, *texts: str | None) -> date | None:
    for text in texts:
        if not text or not isinstance(text, str):
            continue
        lowered = text.lower()
        if "hiệu lực" not in lowered:
            continue
        for pattern in [
            r'(?:có\s+)?hiệu\s+lực(?:\s+thi\s+hành)?\s+(?:kể\s+)?từ\s+ngày\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(?:có\s+)?hiệu\s+lực(?:\s+thi\s+hành)?\s+(?:kể\s+)?từ\s+ngày\s+(\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4})',
            r'(?:có\s+)?hiệu\s+lực(?:\s+thi\s+hành)?\s+(?:kể\s+)?từ\s+(?:ngày\s+)?ban\s+hành'
        ]:
            m = re.search(pattern, lowered)
            if not m:
                continue
            if m.groups():
                parsed = parse_vn_date(m.group(1))
                if parsed:
                    return parsed
            elif issue_date:
                return issue_date
    return None

def normalize_status(status_raw: str | None) -> str:
    if not status_raw: return "Không xác định"
    s = re.split(r'\d', status_raw.lower())[0].strip()
    if any(kw in s for kw in ["hết hiệu lực một phần", "sửa đổi", "bổ sung"]): return "Hết hiệu lực một phần"
    if any(kw in s for kw in ["hết hiệu lực", "bị hủy bỏ", "bị bãi bỏ"]): return "Hết hiệu lực"
    if any(kw in s for kw in ["còn hiệu lực", "đang áp dụng"]): return "Còn hiệu lực"
    return "Không xác định"

def _is_weak_extracted_title(title: str | None) -> bool:
    if not title:
        return True
    normalized = re.sub(r"\s+", " ", title).strip().upper()
    generic_titles = {"LUẬT", "BỘ LUẬT", "NGHỊ ĐỊNH", "NGHỊ QUYẾT", "THÔNG TƯ", "QUYẾT ĐỊNH", "HIẾN PHÁP", "LỆNH", "SẮC LỆNH"}
    return len(normalized) < 5 or len(normalized) > 350 or normalized in generic_titles


def parse_legal_doc(text: str, **kwargs) -> ParsedLegalDoc:
    """Hàm trung tâm: Ưu tiên bóc tách CAPS Title và tạo UID chuẩn."""
    text = unicodedata.normalize('NFC', text)
    doc_id = kwargs.get("doc_id", "").strip()
    doc_type = kwargs.get("doc_type", "Văn bản")
    title_web = kwargs.get("title_web", "")

    # 1. Ưu tiên bóc tách tiêu đề từ nội dung, fallback title web nếu kết quả quá chung chung
    extracted_title = extract_title_from_text(text)
    final_title = title_web if _is_weak_extracted_title(extracted_title) and title_web else extracted_title or title_web or f"{doc_type} {doc_id}"
    
    issue_date = parse_vn_date(kwargs.get("issue_date_str"))
    summary = kwargs.get("summary")
    effective_date = parse_vn_date(kwargs.get("effective_date_str")) or extract_effective_date_from_text(
        issue_date,
        kwargs.get("effective_date_str"),
        summary,
        text
    )

    doc = ParsedLegalDoc(
        doc_id=doc_id,
        title=final_title.strip(),
        doc_type=doc_type,
        issuing_body=kwargs.get("issuing_body") or infer_issuing_body(doc_id),
        legal_field=kwargs.get("field"),
        issue_date=issue_date,
        effective_date=effective_date,
        signer=kwargs.get("signer"),
        summary=summary,
        download_links=kwargs.get("download_links"),
        url=kwargs.get("url"),
        raw_text=text
    )
    
    # 2. Tạo UID Duy nhất theo công thức đã thống nhất
    issue_date_str = str(doc.issue_date) if doc.issue_date else "unknown"
    uid_parts = [slugify(doc_type), slugify(doc_id), slugify(title_web or doc.title), slugify(issue_date_str)]
    doc.uid = "-".join(filter(None, uid_parts))
    
    doc.status = normalize_status(kwargs.get("status_str")) if "status_str" in kwargs else None
    amendment_source = " ".join([doc.title or "", title_web or "", summary or ""]).lower()
    if any(kw in amendment_source for kw in ["sửa đổi", "bổ sung"]):
        doc.is_amendment = True
        
    return doc

"""
Parser cho bản án tòa án.

Chức năng chính:
  - Trích xuất metadata: case_id, ngày, tiêu đề (về việc gì)
  - Tách bản án thành 4 phần: introduction, case_content, court_reasoning, decision
  - Sử dụng keyword-based splitting
"""
import re
from dataclasses import dataclass


@dataclass
class ParsedCourtCase:
    """Kết quả parse một bản án."""
    uid: str | None = None            # UID duy nhất: CASE_NUM-COURT-DATE
    case_no: str | None = None        # Số hiệu: "122/2026/DS-PT"
    court_name: str | None = None     # Tên tòa án
    case_date: str | None = None      # "YYYY-MM-DD"
    title: str | None = None          # Tiêu đề (Về việc...)
    legal_bases: str = ""             # Toàn bộ khối văn bản căn cứ pháp lý
    decision_items: list[str] = None  # Danh sách chi tiết các khoản quyết định
    raw_text: str = ""
    introduction: str = ""
    case_content: str = ""
    court_reasoning: str = ""
    decision: str = ""

    def __post_init__(self):
        if self.legal_bases is None:
            self.legal_bases = []
        if self.decision_items is None:
            self.decision_items = []


# --- Regex nâng cao ---

# Số hiệu: "Bản án số: 122/2024/HNGĐ-ST"
CASE_NO_PATTERN = re.compile(
    r"(?:Bản\s+án\s+số|Số)\s*[:\s]*(\d+/\d{4}/[A-ZĐ\-\s]+ST|PT|GĐT|TT)",
    re.IGNORECASE,
)

# Ngày ban hành: "Ngày: 14 - 10 - 2025." 
# Hỗ trợ: khoảng trắng, dấu gạch ngang/chấm/xuyệt, dấu chấm cuối câu
CASE_DATE_PATTERN = re.compile(
    r"Ngày\s*[:\s]*([\d\s\/\-–\.]+)(?:\s|$|\n)",
    re.IGNORECASE,
)

# Tòa án: "TÒA ÁN NHÂN DÂN ..." (thường xuất hiện ở dòng đầu hoặc sau NHÂN DANH)
COURT_NAME_PATTERN = re.compile(
    r"T[OÒ]A\s+[ÁA]N\s+NH[ẬÂN]\s+D[ÂÂN].+?(?=\s+Đ[ỘO]C\s+LẬP|\s+C[ỘÔO]NG\s+H[ÒO]A|\n|$)",
    re.IGNORECASE,
)



# -- Các hàm tiện ích ---

def generate_court_acronym(court_name: str) -> str:
    """Tạo tên viết tắt cho Tòa án (giữ lại số)."""
    if not court_name or len(court_name) < 5:
        return "TAND"
    
    # Chuẩn hóa: Khu vực -> KV để xử lý đồng nhất
    name = re.sub(r'khu\s*vực', 'KV', court_name, flags=re.IGNORECASE)
    
    # Loại bỏ các từ thừa
    name = re.sub(r'(Tòa án nhân dân|Tòa án|tỉnh|thành phố|TP|Quận|Huyện|Thị xã)', '', name, flags=re.IGNORECASE).strip()
    
    words = name.split()
    acronym = "TAND"
        
    for w in words:
        if w.isupper(): 
            acronym += w
        elif w.isdigit():
            acronym += w
        elif w == "KV":
            acronym += "KV"
        elif w:
            acronym += w[0].upper()
            
    # Loại bỏ các ký tự không phải chữ/số và đảm bảo không lặp KV
    res = re.sub(r'[^A-Z0-9]', '', acronym)
    return res.replace('KVKV', 'KV')

def parse_date(date_str: str) -> str | None:
    """Chuẩn hóa ngày sang YYYY-MM-DD (xử lý khoảng trắng và dấu chấm)."""
    if not date_str:
        return None
    
    # Làm sạch: loại bỏ khoảng trắng, dấu chấm ở cuối, thay gạch/chấm giữa thành /
    clean_date = re.sub(r'\s+', '', date_str).strip('.')
    clean_date = re.sub(r'[\-–\.]', '/', clean_date)
    
    try:
        from datetime import datetime
        dt = datetime.strptime(clean_date, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def generate_case_uid(case_no: str, court_name: str, case_date: str) -> str:
    """Tạo UID: CASE_NUM-COURT-DATE."""
    clean_no = re.sub(r'[^A-Z0-9]', '', str(case_no))
    court_short = generate_court_acronym(court_name)
    clean_date = str(case_date).replace('-', '') if case_date else "00000000"
    return f"{clean_no}-{court_short}-{clean_date}"

# --- Regex patterns ---

CASE_TITLE_PATTERN = re.compile(
    r"(?:Về\s+việc|V/v)\s*[:\"]?\s*(.+?)(?=\n\n|\n\s*(?:NỘI\s+DUNG|NHẬN\s+ĐỊNH|QUYẾT\s+ĐỊNH|NHÂN\s+DANH|HỘI\s+ĐỒNG|VỚI\s+THÀNH|Với\s+thành|C[ỘÔO]NG\s+H[ÒO]A|ĐỘC\s+LẬP|Độc\s+lập)|$)",
    re.IGNORECASE | re.DOTALL
)

SECTION_PATTERNS = {
    "case_content": re.compile(
        r"^\s*N[ỘÔO]I\s+DUNG\s+V[ỤU]\s+[ÁA]N.*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    "court_reasoning": re.compile(
        r"^\s*NH[ẬẠÂA]N\s+Đ[ỊI]NH\s+C[ỦU]A\s+(?:HỘI\s+ĐỒNG\s+XÉT\s+XỬ|TÒA\s+ÁN|TOÀN?\s+ÁN).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    "decision": re.compile(
        r"^\s*QUY[ẾÊE]T\s+Đ[ỊI]NH\s*[:\s]*$",
        re.MULTILINE | re.IGNORECASE,
    ),
}

def extract_decision_details(decision_text: str):
    """
    Tách Căn cứ pháp lý và Danh sách quyết định chi tiết.
    Sử dụng kỹ thuật Sequential Skeleton Search và One-way Gate từ script gốc.
    """
    if not decision_text:
        return "", []
        
    legal_bases_text = ""
    decision_items = []
    
    # Neo từ khóa xử lý (One-way gate)
    process_anchor = re.search(r'\bX[ửu]\s*:', decision_text, re.IGNORECASE)
    
    if process_anchor:
        # 1. Căn cứ pháp lý là phần trước anchor
        legal_bases_text = decision_text[:process_anchor.start()].strip()
        legal_bases_text = re.sub(r'^QUY[ẾÊE]T\s+Đ[ỊI]NH\s*:?\s*', '', legal_bases_text, flags=re.IGNORECASE).strip()
        
        decision_content = decision_text[process_anchor.start():].strip()
        
        # 2. Sequential Skeleton Search (Đánh số 1. 2. 3.)
        items_raw = []
        current_idx = 1
        
        # Tìm điểm bắt đầu thực sự (phần text mô tả chung trước số 1.)
        first_num = re.search(r'(?:\n|^)1\.\s+', decision_content)
        if first_num:
            intro_text = decision_content[:first_num.start()].strip()
            if intro_text:
                items_raw.append(intro_text)
            
            search_text = decision_content[first_num.start():]
            while True:
                next_val = current_idx + 1
                next_num = re.search(rf'(?:\n|^){next_val}\.\s+', search_text)
                if next_num:
                    items_raw.append(search_text[:next_num.start()].strip())
                    search_text = search_text[next_num.start():]
                    current_idx += 1
                else:
                    items_raw.append(search_text.strip())
                    break
        else:
            items_raw.append(decision_content)
            
        decision_items = [i for i in items_raw if i]
    else:
        # Fallback nếu không có "Xử:"
        if len(decision_text) < 800:
            legal_bases_text = decision_text
        else:
            decision_items = [decision_text]
            
    return legal_bases_text, decision_items

def extract_case_metadata(text: str) -> dict:
    header = text[:1000]
    metadata = {
        "case_no": None,
        "court_name": None,
        "case_date": None,
        "title": None
    }

    # Số hiệu
    m_no = CASE_NO_PATTERN.search(header)
    if m_no:
        metadata["case_no"] = m_no.group(1).strip()

    # Tòa án: Ưu tiên tìm trong phần "NHÂN DANH"
    nhan_danh_match = re.search(r'NHÂN\s+DANH\s+NƯỚC\s+CỘNG\s+HÒA\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM\s*[\r\n]+(?:\s*[\r\n]+)*(T[OÒ]A\s+ÁN\s+NH[ẬÂN]\s+D[ÂÂN][^\r\n]+)', header, re.IGNORECASE)
    if nhan_danh_match:
        metadata["court_name"] = nhan_danh_match.group(1).strip()
    else:
        # Fallback về pattern cũ
        m_court = COURT_NAME_PATTERN.search(header)
        if m_court:
            metadata["court_name"] = m_court.group(0).strip()
            # Thêm dòng tiếp theo nếu có "KHU VỰC"
            next_line = re.search(re.escape(metadata["court_name"]) + r'[\s\r\n]+(KHU\s+VỰC\s+\d+[^\r\n]*)', header, re.IGNORECASE)
            if next_line:
                metadata["court_name"] += " " + next_line.group(1).strip()

    # Ngày tháng
    m_date = CASE_DATE_PATTERN.search(header)
    if m_date:
        metadata["case_date"] = parse_date(m_date.group(1).strip())
    else:
        m_date_vn = re.search(r'ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)', header, re.IGNORECASE)
        if m_date_vn:
            d, m, y = m_date_vn.groups()
            metadata["case_date"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    # Tiêu đề
    m_title = CASE_TITLE_PATTERN.search(header)
    if m_title:
        raw_title = m_title.group(1).strip().strip('"""')
        metadata["title"] = re.sub(r"\s+", " ", raw_title)

    return metadata

def split_case_sections(text: str) -> dict:
    sections = {"introduction": "", "case_content": "", "court_reasoning": "", "decision": ""}
    
    section_positions = []
    for section_name, pattern in SECTION_PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            final_match = matches[-1]
            section_positions.append((final_match.start(), final_match.end(), section_name))

    section_positions.sort(key=lambda x: x[0])

    if not section_positions:
        sections["introduction"] = text
        return sections

    sections["introduction"] = text[:section_positions[0][0]].strip()

    for i, (start, end, name) in enumerate(section_positions):
        next_start = section_positions[i + 1][0] if i + 1 < len(section_positions) else len(text)
        sections[name] = text[end:next_start].strip()

    return sections

def parse_court_case(text: str) -> ParsedCourtCase:
    metadata = extract_case_metadata(text)
    sections = split_case_sections(text)
    
    bases, items = extract_decision_details(sections["decision"])

    uid = generate_case_uid(
        metadata.get("case_no"), 
        metadata.get("court_name"), 
        metadata.get("case_date")
    )

    return ParsedCourtCase(
        uid=uid,
        case_no=metadata.get("case_no"),
        court_name=metadata.get("court_name"),
        case_date=metadata.get("case_date"),
        title=metadata.get("title"),
        legal_bases=bases,
        decision_items=items,
        raw_text=text,
        introduction=sections["introduction"],
        case_content=sections["case_content"],
        court_reasoning=sections["court_reasoning"],
        decision=sections["decision"],
    )

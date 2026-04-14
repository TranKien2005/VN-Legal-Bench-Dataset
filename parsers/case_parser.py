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
    case_id: str | None = None       # "122/2026/DS-PT"
    title: str | None = None          # "Tranh chấp hợp đồng tín dụng"
    case_date: str | None = None      # "09-02-2026" (raw, chưa parse date)
    raw_text: str = ""
    introduction: str = ""
    case_content: str = ""
    court_reasoning: str = ""
    decision: str = ""


# --- Regex patterns ---

# Case ID: "Bản án số: 122/2024/HNGĐ-ST" hoặc "Số: 122/2024/HNGĐ-ST"
CASE_ID_PATTERN = re.compile(
    r"(?:Bản\s+án\s+số|Số)\s*[:\s]*(\d+/\d{4}/[A-Za-zĐđ\-]+)",
    re.IGNORECASE,
)

# Ngày: "Ngày: 18/12/2024" hoặc "Ngày 18 tháng 12 năm 2024"
CASE_DATE_PATTERNS = [
    # "Ngày: 18/12/2024" hoặc "Ngày 18-12-2024"
    re.compile(
        r"Ngày\s*[:\s]*(\d{1,2})\s*[\/\-–]\s*(\d{1,2})\s*[\/\-–]\s*(\d{4})",
        re.IGNORECASE,
    ),
    # "ngày 18 tháng 12 năm 2024"
    re.compile(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        re.IGNORECASE,
    ),
]

# Tiêu đề vụ án: 'Về việc "Tranh chấp hợp đồng tín dụng"'
# hoặc: "V/v: Tranh chấp hợp đồng tín dụng"
CASE_TITLE_PATTERNS = [
    re.compile(
        r"(?:Về\s+việc|V/v)\s*[:\"]?\s*(.+?)(?=\n\n|\n\s*(?:NỘI\s+DUNG|NHẬN\s+ĐỊNH|QUYẾT\s+ĐỊNH|NHÂN\s+DANH|HỘI\s+ĐỒNG|VỚI\s+THÀNH|Với\s+thành|C[ỘÔO]NG\s+H[ÒO]A|ĐỘC\s+LẬP|Độc\s+lập)|$)",
        re.IGNORECASE | re.DOTALL
    ),
]

# Keywords cho các phần chính (case-insensitive)
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
        r"^\s*QUY[ẾÊE]T\s+Đ[ỊI]NH\s*[:\s]*$", # Phải là dòng QUYẾT ĐỊNH: đứng độc lập
        re.MULTILINE | re.IGNORECASE,
    ),
}



def extract_case_metadata(text: str) -> dict:
    """
    Trích xuất metadata từ phần đầu bản án.

    Args:
        text: Raw text bản án.

    Returns:
        Dict với keys: case_id, title, case_date.
    """
    # Chỉ tìm trong 3000 ký tự đầu
    header = text[:3000]
    metadata = {"case_id": None, "title": None, "case_date": None}

    # Case ID
    match = CASE_ID_PATTERN.search(header)
    if match:
        metadata["case_id"] = match.group(1).strip()

    # Date
    for pattern in CASE_DATE_PATTERNS:
        match = pattern.search(header)
        if match:
            day, month, year = match.group(1), match.group(2), match.group(3)
            metadata["case_date"] = f"{day.zfill(2)}-{month.zfill(2)}-{year}"
            break

    # Title
    for pattern in CASE_TITLE_PATTERNS:
        match = pattern.search(header)
        if match:
            raw_title = match.group(1).strip().strip('"""')
            # Thay thế tất cả các ký tự khoảng trắng dư thừa và dòng mới thành 1 dấu cách duy nhất
            metadata["title"] = re.sub(r"\s+", " ", raw_title)
            break

    return metadata


def split_case_sections(text: str) -> dict:
    """
    Tách bản án thành 4 phần dựa trên keywords.

    Thứ tự: introduction → NỘI DUNG VỤ ÁN → NHẬN ĐỊNH CỦA TÒA ÁN → QUYẾT ĐỊNH

    Args:
        text: Raw text bản án.

    Returns:
        Dict với keys: introduction, case_content, court_reasoning, decision.
    """
    sections = {
        "introduction": "",
        "case_content": "",
        "court_reasoning": "",
        "decision": "",
    }

    # Tìm vị trí bắt đầu của mỗi section
    # Quan trọng: Loại bỏ các keyword lừa như "Quyết định đưa vụ án ra xét xử"
    valid_text = text
    
    section_positions = []
    for section_name, pattern in SECTION_PATTERNS.items():
        # Riêng phần QUYẾT ĐỊNH, ta chỉ lấy match cuối cùng hoặc match có dấu hai chấm đứng riêng
        matches = list(pattern.finditer(valid_text))
        if matches:
            # Ưu tiên match cuối cùng hoặc match có kết cấu QUYẾT ĐỊNH: (dòng riêng)
            # Trong thực tế, QUYẾT ĐỊNH nằm ở gần cuối bản án.
            final_match = matches[-1]
            section_positions.append((final_match.start(), final_match.end(), section_name))

    # Sắp xếp theo vị trí xuất hiện
    section_positions.sort(key=lambda x: x[0])

    if not section_positions:
        # Không tìm thấy keyword nào → toàn bộ text là introduction
        sections["introduction"] = text
        return sections

    # Introduction = từ đầu đến section đầu tiên
    sections["introduction"] = text[:section_positions[0][0]].strip()

    # Mỗi section = từ sau keyword đến đầu section tiếp theo
    for i, (start, end, name) in enumerate(section_positions):
        next_start = (
            section_positions[i + 1][0]
            if i + 1 < len(section_positions)
            else len(text)
        )
        sections[name] = text[end:next_start].strip()

    return sections




def parse_court_case(text: str) -> ParsedCourtCase:
    """
    Parse toàn bộ bản án.

    Trích xuất metadata và tách thành 4 phần.

    Args:
        text: Raw text đầy đủ của bản án (từ PDF hoặc file text).

    Returns:
        ParsedCourtCase chứa đầy đủ thông tin.
    """
    metadata = extract_case_metadata(text)
    sections = split_case_sections(text)

    return ParsedCourtCase(
        case_id=metadata["case_id"],
        title=metadata["title"],
        case_date=metadata["case_date"],
        raw_text=text,
        introduction=sections["introduction"],
        case_content=sections["case_content"],
        court_reasoning=sections["court_reasoning"],
        decision=sections["decision"],
    )

import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Thêm project root vào path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.case_parser import parse_court_case
from config.settings import settings

def generate_court_acronym(court_raw):
    """
    Tạo tên viết tắt cho tòa án (Acronym).
    VD: Tòa án nhân dân huyện Yên Lập -> TANDHYL
    """
    if not court_raw:
        return "UNKNOWN"
    
    # Chuẩn hóa về không dấu và loại bỏ phần trong ngoặc đơn
    def simplify(text):
        # Loại bỏ ngoặc đơn
        text = re.sub(r'\(.*?\)', '', text)
        # Bảng chuyển đổi cơ bản (để tránh dependency phức tạp)
        v_chars = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
        e_chars = "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
        res = ""
        for char in text.lower():
            if char in v_chars:
                res += e_chars[v_chars.index(char)]
            else:
                res += char
        return res

    text = simplify(court_raw)
    
    # Các từ khóa viết tắt cố định
    replacements = {
        "toa an nhan dan": "TAND",
        "vien kiem sat": "VKS",
        "cap cao": "CC",
        "phuc tham": "PT",
        "so tham": "ST",
        "thanh pho": "TP",
        "huyen": "H",
        "tinh": "T",
        "quan": "Q",
        "thi xa": "TX"
    }
    
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    # Lấy các chữ cái đầu của các từ còn lại
    words = text.split()
    acronym = ""
    for w in words:
        if w.isupper(): # Giữ nguyên các phần đã viết tắt như TAND
            acronym += w
        else:
            acronym += w[0].upper()
            
    return re.sub(r'[^A-Z]', '', acronym)

def extract_header_info(text):
    """
    Bóc tách thông tin từ header văn bản bằng kỹ thuật Neo từ khóa (Anchor-based).
    """
    header_block = "\n".join(text.split("\n")[:50]) # Quét 50 dòng đầu
    
    info = {
        "court_name": None,
        "case_number": None,
        "issuance_date": None,
        "title_parsed": None
    }
    
    # 1. Tìm Tòa án (CAPS Block Identification)
    # Tìm dòng bắt đầu bằng TOÀ ÁN hoặc TÒA ÁN
    court_match = re.search(r'T[OÒ]À\s+ÁN\s+NHÂN\s+DÂN\s+([^\n]+)', header_block, re.IGNORECASE)
    if court_match:
        info["court_name"] = court_match.group(0).strip()
        
    # 2. Tìm Số hiệu (Regex anchor)
    num_match = re.search(r'(?:Bản\s+án\s+số|Số)\s*[:\s]*([^\s\n]+)', header_block, re.IGNORECASE)
    if num_match:
        info["case_number"] = num_match.group(1).strip()
        
    # 3. Tìm Ngày ban hành (Regex anchor)
    date_match = re.search(r'Ngày\s*[:\s]*([\d\/\-–\.]+)', header_block, re.IGNORECASE)
    if not date_match:
        date_text_match = re.search(r'ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)', header_block, re.IGNORECASE)
        if date_text_match:
            d, m, y = date_text_match.groups()
            info["issuance_date"] = f"{d.zfill(2)}/{m.zfill(2)}/{y}"
    else:
        # Chuẩn hóa về /
        raw_date = date_match.group(1).strip()
        info["issuance_date"] = re.sub(r'[\-–\.]', '/', raw_date)
        
    # 4. Tìm Tiêu đề vụ án (V/v)
    title_match = re.search(r'(?:V/v|Về\s+việc)\s*[:\s]*([^\n]+)', header_block, re.IGNORECASE)
    if title_match:
        info["title_parsed"] = title_match.group(1).strip()
        
    return info

def extract_decision_details(decision_text):
    """
    Tách Căn cứ pháp lý và Danh sách quyết định chi tiết.
    Sử dụng kỹ thuật Sequential Skeleton Search và One-way Gate.
    """
    if not decision_text:
        return None, []
        
    legal_bases = ""
    decision_items = []
    
    # Neo từ khóa xử lý (One-way gate)
    # Search for "Xử:" or "QUYẾT ĐỊNH:" case-insensitively
    process_anchor = re.search(r'\bX[ửu]\s*:', decision_text, re.IGNORECASE)
    
    if process_anchor:
        # Căn cứ pháp lý là phần trước anchor
        legal_bases = decision_text[:process_anchor.start()].strip()
        # Loại bỏ các prefix "Căn cứ..." nếu nó lặp lại tiêu đề QUYẾT ĐỊNH
        legal_bases = re.sub(r'^QUY[ẾÊE]T\s+Đ[ỊI]NH\s*:?\s*', '', legal_bases, flags=re.IGNORECASE).strip()
        
        # Nội dung xử lý
        decision_content = decision_text[process_anchor.start():].strip()
        
        # 2. Sequential Skeleton Search (Đánh số 1. 2. 3.)
        # Tìm item phát sinh đầu tiên (thường là sau Xử:)
        items_raw = []
        
        # Regex tìm các điểm bắt đầu: \n1., \n2. hoặc ^1.
        # Nhưng để tránh bắt nhầm, ta dùng logic tuần tự
        current_idx = 1
        last_pos = 0
        
        # Tìm điểm bắt đầu thực sự (phần text mô tả chung trước số 1.)
        first_num = re.search(r'(?:\n|^)1\.\s+', decision_content)
        if first_num:
            intro_text = decision_content[:first_num.start()].strip()
            if intro_text:
                items_raw.append(intro_text)
            
            # Quét tuần tự
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
        # Nếu không có từ khóa "Xử:", coi toàn bộ là căn cứ hoặc item tùy ngữ cảnh
        # Ở đây tạm để vào bases nếu ngắn, không thì để items
        if len(decision_text) < 500:
            legal_bases = decision_text
        else:
            decision_items = [decision_text]
            
    return legal_bases, decision_items

def parse_date(date_str):
    """Chuẩn hóa ngày sang YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        # Hỗ trợ DD/MM/YYYY
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return None

def process_raw_data(raw_json_path):
    with open(raw_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    processed_results = []
    
    for item in data:
        raw_text = item.get("raw_text", "")
        if not raw_text.strip():
            continue
            
        web_meta = item.get("metadata", {})
        
        # 0. Kiểm tra bộ lọc: Áp dụng án lệ & Đính chính
        # Nếu có nội dung (không phải placeholder) thì bỏ qua
        case_law = web_meta.get("Áp dụng án lệ", "")
        if case_law and "Đăng nhập" not in case_law and len(case_law) > 50:
            continue
            
        correction = web_meta.get("Đính chính", "")
        if correction and "Đăng nhập" not in correction and len(correction) > 50:
            continue

        # 1. Parse cấu trúc cơ bản (4 phần)
        parsed = parse_court_case(raw_text)
        
        # 2. Trích xuất Header thông minh (Ưu tiên 1)
        header_info = extract_header_info(raw_text)
        
        # 3. Ưu tiên nguồn dữ liệu & Fallback
        case_number = header_info["case_number"] or web_meta.get("Số hiệu")
        court_name = header_info["court_name"] or web_meta.get("Tòa án xét xử")
        issuance_date_str = header_info["issuance_date"] or web_meta.get("Ngày ban hành")
        issuance_date = parse_date(issuance_date_str)
        
        title_parsed = header_info["title_parsed"] or parsed.title
        
        # 4. Tạo UID
        court_acronym = generate_court_acronym(court_name)
        date_part = issuance_date if issuance_date else "0000-00-00"
        clean_num = re.sub(r'[^a-zA-Z0-9]', '', str(case_number))
        uid = f"{clean_num}-{court_acronym}-{date_part}"
        
        # 5. Trích xuất Căn cứ pháp lý & Quyết định chi tiết
        legal_bases, decision_items = extract_decision_details(parsed.decision)
        
        # 6. Tạo Flat Schema
        result = {
            "uid": uid,
            "case_number": case_number,
            "court_name": court_name,
            "issuance_date": issuance_date,
            "title_web": web_meta.get("Tên Bản án"),
            "title_parsed": title_parsed,
            "legal_relation": web_meta.get("Quan hệ pháp luật"),
            "court_level": web_meta.get("Cấp xét xử"),
            "case_type": web_meta.get("Lĩnh vực"),
            "case_info": web_meta.get("Thông tin về vụ/việc"),
            "source_url": item.get("url"),
            "source_doc_url": web_meta.get("docx_url") or web_meta.get("pdf_url"),
            "summary": web_meta.get("summary"),
            "legal_bases": legal_bases,
            "decision_items": decision_items,
            "case_date": parsed.case_date, # Ngày trích xuất từ text (incidents)
            "raw_text": raw_text,
            "section_introduction": parsed.introduction,
            "section_content": parsed.case_content,
            "section_reasoning": parsed.court_reasoning,
            "section_decision": parsed.decision
        }
        processed_results.append(result)
        
    return processed_results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/process_luatvietnam_banan.py <path_to_raw_json>")
        sys.exit(1)
        
    raw_path = Path(sys.argv[1])
    if not raw_path.exists():
        print(f"File not found: {raw_path}")
        sys.exit(1)
        
    results = process_raw_data(raw_path)
    
    # Lưu kết quả đã xử lý (giữ nguyên tên file để dễ tham chiếu)
    output_path = settings.PROCESSED_DIR / "court_cases" / raw_path.name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"--- ĐÃ XỬ LÝ XONG {len(results)} bản án ---")
    print(f"Kết quả lưu tại: {output_path}")

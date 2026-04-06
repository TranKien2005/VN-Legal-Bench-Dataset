"""
Parser cho văn bản quy phạm pháp luật.

Chức năng chính:
  - Trích xuất doc_id từ dòng "Luật số: XX/YYYY/QH..." hoặc "Số: XX/YYYY/NĐ-CP"
  - Tách văn bản thành các điều (article)
  - Tạo article_id = doc_id + "_D" + article_number
"""
import re
from dataclasses import dataclass, field


@dataclass
class ParsedArticle:
    """Một điều khoản đã được parse."""
    article_number: str       # "2", "33", "33a"
    title: str | None = None  # "Mục tiêu giáo dục" (tên điều, nếu có)
    content: str = ""         # Toàn bộ nội dung điều (bao gồm cả tiêu đề)


@dataclass
class ParsedLegalDoc:
    """Kết quả parse một văn bản quy phạm pháp luật."""
    doc_id: str | None = None          # "43/2019/QH14"
    raw_text: str = ""                  # Full text
    articles: list[ParsedArticle] = field(default_factory=list)


# --- Regex patterns ---

# Tìm mã số văn bản: "Luật số: 43/2019/QH14", "Số: 74/2015/NĐ-CP"
# Cũng match: "LUẬT SỐ: 43/2019/QH14"
DOC_ID_PATTERNS = [
    # "Luật số: 43/2019/QH14" hoặc "Số: 43/2019/QH14"
    re.compile(
        r"(?:Luật\s+số|Pháp\s+lệnh\s+số|Số)\s*:\s*(\d+/\d{4}/[A-Za-zĐđ\-]+\d*)",
        re.IGNORECASE,
    ),
    # Backup: tìm pattern XX/YYYY/XX đứng riêng
    re.compile(r"\b(\d+/\d{4}/[A-Za-zĐđ\-]+\d*)\b"),
]

# Tìm đầu mỗi điều: "Điều 2.", "Điều 33.", "Điều 33a."
# Phải bắt đầu dòng hoặc sau newline
ARTICLE_PATTERN = re.compile(
    r"^(Điều\s+(\d+\w*)\.\s*(.*))",
    re.MULTILINE,
)


def extract_doc_id(text: str) -> str | None:
    """
    Trích xuất mã số văn bản (doc_id) từ text.

    Tìm pattern "Luật số: XX/YYYY/ZZZZ" hoặc "Số: XX/YYYY/ZZZZ"
    thường xuất hiện ở trang đầu tiên.

    Args:
        text: Raw text của văn bản.

    Returns:
        doc_id string (VD: "43/2019/QH14") hoặc None nếu không tìm thấy.
    """
    # Chỉ tìm trong 2000 ký tự đầu (trang đầu)
    header = text[:2000]

    for pattern in DOC_ID_PATTERNS:
        match = pattern.search(header)
        if match:
            return match.group(1).strip()

    return None


def split_articles(text: str) -> list[ParsedArticle]:
    """
    Tách văn bản thành danh sách các điều khoản.

    Mỗi điều bắt đầu bằng "Điều X." và kết thúc tại "Điều X+1."
    hoặc cuối văn bản.

    Args:
        text: Raw text của văn bản.

    Returns:
        Danh sách ParsedArticle.
    """
    matches = list(ARTICLE_PATTERN.finditer(text))

    if not matches:
        return []

    articles = []

    for i, match in enumerate(matches):
        article_number = match.group(2).strip()
        article_title_line = match.group(3).strip() or None

        # Nội dung: từ đầu điều đến đầu điều tiếp theo
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        articles.append(ParsedArticle(
            article_number=article_number,
            title=article_title_line,
            content=content,
        ))

    return articles


def parse_legal_doc(text: str) -> ParsedLegalDoc:
    """
    Parse toàn bộ văn bản quy phạm pháp luật.

    Trích xuất doc_id và tách thành các điều khoản.

    Args:
        text: Raw text đầy đủ của văn bản (từ PDF hoặc file text).

    Returns:
        ParsedLegalDoc chứa doc_id, raw_text, và danh sách articles.
    """
    doc_id = extract_doc_id(text)
    articles = split_articles(text)

    return ParsedLegalDoc(
        doc_id=doc_id,
        raw_text=text,
        articles=articles,
    )

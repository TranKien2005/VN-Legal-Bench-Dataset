import requests
from bs4 import BeautifulSoup
import docx
import io
import json
import time
import random
import pdfplumber
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Import config
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

class LuatVietnamEngine:
    def __init__(self, num_workers=3):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://luatvietnam.vn/ban-an/tim-ban-an.html"
        })
        self.base_url = "https://luatvietnam.vn"
        self.num_workers = num_workers
        self.raw_dir = settings.RAW_DIR / "court_cases"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.min_char_count = 1000  # Ngưỡng tối thiểu 1000 chữ theo yêu cầu

    def extract_docx_text(self, content_bytes):
        """Trích xuất text từ file docx trong RAM."""
        try:
            doc = docx.Document(io.BytesIO(content_bytes))
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return "\n".join(full_text)
        except Exception as e:
            print(f"  [LỖI] Không thể đọc docx: {e}")
            return ""

    def extract_pdf_text(self, content_bytes):
        """Trích xuất text từ file PDF trong RAM bằng pdfplumber."""
        try:
            full_text = []
            with pdfplumber.open(io.BytesIO(content_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
            return "\n".join(full_text)
        except Exception as e:
            print(f"  [LỖI] Không thể đọc PDF: {e}")
            return ""

    def scrape_detail_page(self, detail_url):
        """Cào trang chi tiết (Thuộc tính, Tóm tắt và file nội dung)."""
        try:
            response = self.session.get(detail_url, timeout=30)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            doc_record = {
                "url": detail_url,
                "scraped_at": datetime.now().isoformat(),
                "metadata": {
                    "summary": "",
                    "pdf_url": None,
                    "docx_url": None
                },
                "raw_text": ""
            }

            # 1. Lấy Metadata từ bảng Thuộc tính
            attr_table = soup.find('table', class_='table-thuoc-tinh')
            if not attr_table:
                attr_table = soup.find('table', class_='table-attribute')
            if not attr_table:
                attr_table = soup.find('table')

            # Initialize all required metadata fields with None
            doc_record["metadata"].update({
                "Số hiệu": None,
                "Ngày ban hành": None,
                "Lĩnh vực": None,
                "Tòa án xét xử": None,
                "Quan hệ pháp luật": None,
                "Cấp xét xử": None,
                "Loại văn bản": None,
                "Người ký": None,
                "summary": None,
                "pdf_url": None,
                "docx_url": None,
                "source_format": None
            })

            if attr_table:
                for row in attr_table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True).replace(':', '')
                        val = cells[1].get_text(separator=' ', strip=True)
                        doc_record["metadata"][key] = val
            
            # 2. Lấy Tóm tắt (Tóm tắt Bản án)
            import re
            summary_label = soup.find(lambda tag: tag.name == "div" and "doc-headding" in tag.get("class", []) and re.search(r"Tóm tắt Bản án", tag.text, re.I))
            if summary_label:
                # Tìm block tiếp theo có chứa document-body
                summary_block = summary_label.find_parent('div', class_='block').find_next_sibling('div', class_='block')
                if summary_block:
                    body = summary_block.find('div', class_='document-body')
                    if body:
                        doc_record["metadata"]["summary"] = body.get_text(strip=True)

            # 3. Tìm link tải file (DOCX và PDF)
            download_blocks = soup.find_all('div', class_='list-download')
            for block in download_blocks:
                a = block.find('a', href=True)
                if a:
                    href = a['href']
                    if not href.startswith('http'):
                        href = self.base_url + href
                    
                    if href.lower().endswith('.docx'):
                        doc_record["metadata"]["docx_url"] = href
                    elif href.lower().endswith('.pdf'):
                        doc_record["metadata"]["pdf_url"] = href

            # 4. Xử lý lấy nội dung văn bản (raw_text) với fallback
            final_text = ""
            source_used = None

            # Thử DOCX trước
            if doc_record["metadata"]["docx_url"]:
                print(f"  -> Thử tải DOCX: {doc_record['metadata']['docx_url']}")
                try:
                    res = self.session.get(doc_record["metadata"]["docx_url"], timeout=60)
                    if res.status_code == 200:
                        text = self.extract_docx_text(res.content)
                        if len(text) >= self.min_char_count:
                            final_text = text
                            source_used = "docx"
                except Exception as e:
                    print(f"  [!] Lỗi tải/đọc DOCX: {e}")

            # Fallback sang PDF nếu DOCX thất bại hoặc không đủ dài
            if len(final_text) < self.min_char_count and doc_record["metadata"]["pdf_url"]:
                print(f"  -> Thử tải PDF (fallback): {doc_record['metadata']['pdf_url']}")
                try:
                    res = self.session.get(doc_record["metadata"]["pdf_url"], timeout=60)
                    if res.status_code == 200:
                        text = self.extract_pdf_text(res.content)
                        if len(text) >= self.min_char_count:
                            final_text = text
                            source_used = "pdf"
                except Exception as e:
                    print(f"  [!] Lỗi tải/đọc PDF: {e}")

            if len(final_text) < self.min_char_count:
                print(f"  [!] Bỏ qua bản án: Nội dung quá ngắn ({len(final_text)} ký tự).")
                return None  # Bỏ qua hoàn toàn vụ án này

            doc_record["raw_text"] = final_text
            doc_record["metadata"]["source_format"] = source_used
            
            print(f"  -> Thành công: Lấy được {len(final_text)} ký tự từ {source_used}.")
            return doc_record
        except Exception as e:
            print(f"  [LỖI] Lỗi trang chi tiết {detail_url}: {e}")
            return None

    def scrape_search_page(self, params):
        """Lấy danh sách link và tiêu đề bản án từ trang tìm kiếm."""
        try:
            search_url = f"{self.base_url}/ban-an/tim-ban-an.html"
            response = self.session.get(search_url, params=params, timeout=30)
            if response.status_code != 200:
                print(f"  [LỖI] Không thể access trang tìm kiếm (Status {response.status_code})")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            title_containers = soup.find_all('h3', class_='entry-title')
            for h3 in title_containers:
                a = h3.find('a', href=True)
                if a:
                    full_link = a['href']
                    if not full_link.startswith('http'):
                        full_link = self.base_url + full_link
                    
                    # Chỉ lấy các link bản án
                    if "/ban-an/" in full_link:
                        results.append({
                            "url": full_link,
                            "title": a.get_text(separator=' ', strip=True)
                        })
            
            if not results:
                # Thử selector khác rộng hơn
                items = soup.select('div.doc-item h3 a[href]')
                for a in items:
                    href = a['href']
                    if "/ban-an/" in href:
                         results.append({
                            "url": self.base_url + href if not href.startswith('http') else href,
                            "title": a.get_text(separator=' ', strip=True)
                        })

            print(f"  -> Tìm thấy {len(results)} bản án trên trang này.")
            return results

        except Exception as e:
            print(f"  [LỖI] Lỗi trang tìm kiếm: {e}")
            return []

    def run(self, max_pages=1, start_page=1, custom_params=None):
        """Chạy quy trình cào dữ liệu."""
        default_params = {
            "SearchKeyword": "",
            "DateFrom": "01/01/2010",
            "DateTo": datetime.now().strftime("%d/%m/%Y"),
            "IsSearchExact": "0",
            "SearchByDate": "publishDate",
            "CourtLevelId": "0",
            "CourtId": "0",
            "JudicialLevelId": "1",
            "LawJudgTypeId": "1",
            "CateId": "0",
            "LegalRelationId": "0",
            "TypeSearch": "0"
        }
        
        if custom_params:
            default_params.update(custom_params)

        print(f"[*] Tham số tìm kiếm: {default_params}")

        # Mồi cookie trang chủ trước
        self.session.get(self.base_url)

        for page in range(start_page, start_page + max_pages):
            print(f"\n[*] Đang cào trang {page}...")
            page_params = default_params.copy()
            page_params["Page"] = page
            
            links = self.scrape_search_page(page_params)
            if not links:
                print(f"  [!] Không tìm thấy thêm liên kết nào ở trang {page}. Dừng.")
                break
            
            page_results = []
            for link in links:
                print(f"  [*] Đang xử lý: {link}")
                result = self.scrape_detail_page(link)
                if result:
                    page_results.append(result)
                time.sleep(random.uniform(1, 3))
            
            if page_results:
                # Tạo tên file gợi nhớ dựa trên tham số
                kw = default_params.get("SearchKeyword") or "none"
                kw_clean = "".join([c if c.isalnum() else "_" for c in kw])
                d_from = default_params.get("DateFrom", "").replace("/", "")
                d_to = default_params.get("DateTo", "").replace("/", "")
                
                filename = f"luatvietnam_K-{kw_clean}_F-{d_from}_T-{d_to}_P-{page}.json"
                output_path = self.raw_dir / filename
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(page_results, f, ensure_ascii=False, indent=2)
                print(f"--- Đã lưu {len(page_results)} bản án vào {filename} ---")
            
            if page < start_page + max_pages - 1:
                wait_time = random.uniform(3, 7)
                print(f"[*] Nghỉ {wait_time:.1f} giây trước khi sang trang tiếp theo...")
                time.sleep(wait_time)

        print("\n[KẾT THÚC] Hoàn tất quá trình cào dữ liệu.")

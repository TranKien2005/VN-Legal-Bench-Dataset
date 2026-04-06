import os
import json
import time
import argparse
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


#Chạy trước khi chạy scirpt
#PS D:\My Works\Coding\VN-Legal-Bench-Dataset> & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"
def get_issuing_body(doc_id):
    parts = doc_id.split('/')
    if not parts:
        return ""
    suffix = parts[-1].strip().upper()
    if suffix.startswith("QH"):
        return "Quốc hội"
    elif suffix.startswith("UBTVQH"):
        return "Ủy ban Thường vụ Quốc hội"
    elif suffix.startswith("NĐ-CP") or suffix == "CP":
        return "Chính phủ"
    return suffix

def scrape(max_pages):
    base_url = "https://vanbanphapluat.co/csdl/van-ban-phap-luat"
    results = []
    
    with sync_playwright() as p:
        try:
            print("Đang kết nối tới Chrome của bạn qua cổng 9222...")
            # Sử dụng 127.0.0.1 thay vì localhost để tránh lỗi phân giải IPv6 trên Windows
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print(f"Không thể kết nối. Lỗi: {e}")
            print("Bạn chưa mở Chrome ở chế độ Debug! Hãy kiểm tra lại dòng lệnh đã chạy.")
            return

        page_context = browser.contexts[0]
        page = page_context.new_page()
        
        for p_num in range(1, max_pages + 1):
            results = []  # Reset kết quả cho mỗi trang riêng biệt
            print(f"Scraping page {p_num}...")
            url = f"{base_url}?l=luat&p={p_num}"
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("Đang tải (hoặc chờ bạn ấn Verify trên cửa sổ Chrome đang mở)...")
                
                # Vòng lặp chờ nội dung xuất hiện, giúp script tự động chạy khi bạn ấn captcha xong
                for _ in range(30):
                    content = page.content()
                    if 'Ban hành:' in content:
                        print("-> Đã tải xong nội dung!")
                        break
                    time.sleep(2)
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")
                break
                
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            blocks = soup.find_all('div', class_='row')
            unique_blocks = []
            
            for b in blocks:
                # Mỗi box chuẩn đều phải có h4 chứa link và div chức push-30 chứa title
                if b.find('h4') and b.find('div', class_='push-30') and b.find(string=lambda t: t and 'Ban hành:' in t):
                    # Vì .row có thể lồng nhau, ta kiểm tra xem nó có đúng là thẻ bọc ngoài cùng không
                    # Thẻ bọc ngoài cùng sẽ chứa class col-md-9
                    if b.find('div', class_='col-md-9 col-sm-8'):
                        unique_blocks.append(b)

            if not unique_blocks:
                print("No list blocks found on page", p_num)
                break

            seen_hrefs = set()
            for mem in unique_blocks:
                anchor = mem.find('h4').find('a')
                if not anchor:
                    continue
                
                href = anchor.get('href')
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                
                full_link = f"https://vanbanphapluat.co{href}" if href.startswith('/') else f"https://vanbanphapluat.co/{href}"
                
                # Lấy doc_id từ href hoặc text
                raw_doc_id = anchor.text.strip()
                
                # Bỏ qua "dự thảo" hoặc các tên không đúng cấu trúc ban hành chuẩn (số/năm/cơ quan)
                import re
                if 'dự thảo' in raw_doc_id.lower() or not re.search(r'\d+/\d+/[A-Z0-9]+', raw_doc_id):
                    print(f"Skipping draft/invalid doc: {raw_doc_id}")
                    continue
                
                doc_id = raw_doc_id
                if doc_id.lower().startswith("luật "):
                    doc_id = doc_id[5:].strip()
                elif doc_id.lower().startswith("hiến pháp "):
                    doc_id = doc_id[10:].strip()
                    
                # Lấy Title
                title_div = mem.find('div', class_='push-30')
                title = title_div.text.strip() if title_div else ""
                
                issue_date = ""
                effective_date = ""
                status = ""
                
                # Trích xuất metadata
                for div in mem.find_all('div'):
                    text_content = div.text.strip()
                    if "Ban hành:" in text_content and div.find('strong'):
                        issue_date = div.find('strong').text.strip()
                    elif "Ngày hiệu lực:" in text_content and div.find('strong'):
                        effective_date = div.find('strong').text.strip()
                    elif "Hiệu lực:" in text_content and div.find('strong'):
                        status = div.find('strong').text.strip()

                print(f"-> Found: {doc_id} | {title} | {full_link}")
                
                print(f"   Fetching details from {full_link}")
                detail_text = ""
                try:
                    detail_page = page_context.new_page()
                    detail_page.goto(full_link, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(1)
                    detail_soup = BeautifulSoup(detail_page.content(), 'html.parser')
                    toan_van = detail_soup.find(id="toan-van")
                    
                    if toan_van:
                        divs = toan_van.find_all('div', recursive=False)
                        if divs:
                            inner_divs = divs[0].find_all('div', recursive=False)
                            if inner_divs:
                                detail_text = inner_divs[0].get_text(separator='\n', strip=True)
                            else:
                                detail_text = divs[0].get_text(separator='\n', strip=True)
                        else:
                            detail_text = toan_van.get_text(separator='\n', strip=True)
                    else:
                        print("   Could not find #toan-van")
                    detail_page.close()
                except Exception as e:
                    print(f"   Failed to fetch detail: {e}")
                
                item = {
                    "doc_id": doc_id,
                    "title": title,
                    "doc_type": "luật",
                    "issue_date": issue_date,
                    "effective_date": effective_date,
                    "status": status,
                    "issuing_body": get_issuing_body(doc_id),
                    "raw_text": detail_text,
                    "url": full_link
                }
                results.append(item)
                
            # Lưu file cho từng trang
            os.makedirs('d:/My Works/Coding/VN-Legal-Bench-Dataset/data/processed', exist_ok=True)
            out_file = f'd:/My Works/Coding/VN-Legal-Bench-Dataset/data/processed/vanbanphapluat_luat_page_{p_num}.json'
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"Saved {len(results)} items to {out_file}")
                
        # Đóng kết nối của playwright (không tắt Chrome gốc)
        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--max_pages', type=int, default=1, help='Number of pages to scrape')
    args = parser.parse_args()
    
    scrape(args.max_pages)

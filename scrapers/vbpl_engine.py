import os
import json
import asyncio
import sys
import subprocess
import socket
import random
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from config.settings import settings

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

async def ensure_chrome_debug():
    port = settings.CHROME_DEBUG_PORT
    if is_port_in_use(port): return True
    chrome_path = settings.CHROME_PATH
    user_data_dir = settings.CHROME_USER_DATA_DIR
    if not os.path.exists(user_data_dir): os.makedirs(user_data_dir)
    args = [chrome_path, f"--remote-debugging-port={port}", f"--user-data-dir={user_data_dir}"]
    try:
        creation_flags = 0x01000000 | 0x00000200 | 0x00000008 if os.name == 'nt' else 0
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags, close_fds=True)
        for _ in range(15):
            if is_port_in_use(port): return True
            await asyncio.sleep(1)
        return False
    except Exception as e:
        print(f"LỖI Chrome: {e}"); return False

def is_strict_official_title(title: str) -> bool:
    """
    KIỂM TRA TIÊU ĐỀ NGHIÊM NGẶT (Cơ chế lựa chọn đã thống nhất):
    - Chỉ chấp nhận: "Loại_văn_bản + Số_hiệu" (Ví dụ: Luật 35/2024/QH15, Nghị định 143/2024/NĐ-CP)
    - Loại bỏ: Bất kỳ tiêu đề nào có mô tả (Ví dụ: Luật Cảnh vệ sửa đổi, Nghị định về việc...)
    """
    # Loại bớt các từ khóa rác rõ rệt trước
    t_lower = title.lower()
    if any(kw in t_lower for kw in ["dự thảo", "dự kiến", "góp ý", "sửa đổi", "bổ sung", "quy định về", "về việc"]):
        # Ngoại lệ: Nếu "sửa đổi" nằm TRONG số hiệu (hiếm) thì vẫn cần cân nhắc, nhưng theo yêu cầu bạn là không lấy.
        return False
    
    # Định dạng chuẩn: [Loại] [Số/Ký hiệu]
    # Thường là: Luật 12/2023/QH15, Nghị định 12/2023/NĐ-CP, Luật 2/SL
    # Check nếu tiêu đề có chứa khoảng trắng và phần sau có chứa số hoặc gạch chéo
    parts = title.split()
    if len(parts) < 2: return False
    
    # Check phần "Số hiệu" (phần còn lại sau Loại văn bản)
    id_part = " ".join(parts[1:])
    # Nếu có quá nhiều từ (mô tả dài) -> Rác
    if len(parts) > 3: return False 
    
    # Phải có ít nhất một chữ số hoặc dấu gạch chéo/gạch ngang đặc trưng của Số hiệu
    if not any(char.isdigit() for char in id_part) and '/' not in id_part and '-' not in id_part:
        return False
        
    return True

async def scrape_page_task(worker_id, browser_context, p_num, doc_type_slug, base_url, raw_dir):
    p_tag = f"W{worker_id}-P{p_num}"
    print(f"[{p_tag}] Đang xử lý...")
    page = await browser_context.new_page()
    detail_page = await browser_context.new_page()
    
    try:
        url = f"{base_url}?l={doc_type_slug}&p={p_num}"
        await page.goto(url, wait_until="networkidle", timeout=60000)
        page_content = await page.content()
        
        if any(x in page_content.lower() for x in ["verify you are human", "challenge-running", "checking your browser"]):
            return "BLOCKED"

        soup = BeautifulSoup(page_content, 'html.parser')
        blocks = [b for b in soup.find_all('div', class_='row') if b.find('h4')]
        if not blocks: return "EMPTY"

        page_docs = []
        seen_hrefs = set()
        for mem in blocks:
            anchor = mem.find('h4').find('a') if mem.find('h4') else None
            if not anchor: continue
            
            raw_title = anchor.text.strip()
            
            # --- CƠ CHẾ LỰA CHỌN THỐNG NHẤT ---
            if not is_strict_official_title(raw_title):
                continue

            href = anchor.get('href', '').strip().lower().rstrip('/')
            if not href.startswith('http') and not href.startswith('/'): href = '/' + href
            if not href or href in seen_hrefs: continue
            seen_hrefs.add(href)
            
            full_link = f"https://vanbanphapluat.co{href}" if href.startswith('/') else href
            doc_record = {"url": full_link, "title_web": raw_title, "raw_text": ""}
            
            # Cào chi tiết để lấy Metadata thật
            try:
                await detail_page.goto(full_link, wait_until="domcontentloaded", timeout=45000)
                d_content = await detail_page.content()
                if "verify you are human" in d_content.lower(): return "BLOCKED"
                d_soup = BeautifulSoup(d_content, 'html.parser')
                tv = d_soup.find(id="toan-van")
                if tv: doc_record["raw_text"] = tv.get_text(separator='\n', strip=True)
                
                tbl = d_soup.find('table', class_='table-striped')
                if tbl:
                    for row in tbl.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            lbl = cells[0].get_text(strip=True).replace(':', '')
                            # Lấy text từ thẻ <a> nếu có (đúng cơ chế clickable)
                            val_anchor = cells[1].find('a')
                            val = val_anchor.get_text(strip=True) if val_anchor else cells[1].get_text(strip=True)
                            doc_record[lbl] = val
            except: pass

            # Lưu nếu có số hiệu (xác nhận lại độ tin cậy)
            if doc_record.get("Số hiệu") or "/" in raw_title:
                page_docs.append(doc_record)
                print(f"  [{p_tag}] ✓ {raw_title}")

        if not page_docs: return "SUCCESS" 

        file_name = f"vanbanphapluat_{doc_type_slug}_page_{p_num}.json"
        with open(raw_dir / file_name, 'w', encoding='utf-8') as f:
            json.dump(page_docs, f, ensure_ascii=False, indent=2)
        print(f"--- [{p_tag}] Xong ({len(page_docs)} văn bản) ---")
        return "SUCCESS"
    except Exception as e:
        print(f"Lỗi {p_tag}: {e}"); return "RETRYABLE_ERROR"
    finally:
        try: await page.close()
        except: pass
        try: await detail_page.close()
        except: pass

async def worker(worker_id, queue, context, doc_type_slug, base_url, raw_dir, stop_event):
    while not stop_event.is_set():
        try: p_num = queue.get_nowait()
        except asyncio.QueueEmpty: break
        for attempt in range(2):
            if stop_event.is_set(): break
            status = await scrape_page_task(worker_id, context, p_num, doc_type_slug, base_url, raw_dir)
            if status == "SUCCESS": break
            if status == "EMPTY":
                stop_event.set()
                while not queue.empty():
                    try: queue.get_nowait(); queue.task_done()
                    except: break
                break
            if status == "BLOCKED": await asyncio.sleep(60); break
            await asyncio.sleep(5)
        queue.task_done()

async def scrape_vanbanphapluat(max_pages, doc_type_slug="luat", start_page=1, num_workers=3):
    if not await ensure_chrome_debug(): return
    raw_dir = settings.RAW_DIR / "legal_docs"; raw_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        for op in context.pages[1:]:
            try: await op.close()
            except: pass
        count = 9999 if max_pages == "auto" else int(max_pages)
        queue = asyncio.Queue()
        for p_num in range(start_page, start_page + count): await queue.put(p_num)
        stop_event = asyncio.Event()
        base_url = "https://vanbanphapluat.co/csdl/van-ban-phap-luat"
        workers = [asyncio.create_task(worker(i+1, queue, context, doc_type_slug, base_url, raw_dir, stop_event)) for i in range(num_workers)]
        try: await asyncio.gather(*workers)
        except asyncio.CancelledError: stop_event.set()
        finally: print("\n=== KẾT THÚC QUY TRÌNH ===")

async def scrape_special_vbpl(urls):
    """Cào danh sách link đặc biệt chỉ định thủ công."""
    if not await ensure_chrome_debug(): return
    output_dir = settings.RAW_DIR / "legal_docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = await context.new_page()
        
        print(f"=== SCRAPING ĐẶC BIỆT ({len(urls)} văn bản) ===")
        results = []
        for i, url in enumerate(urls):
            print(f"[{i+1}/{len(urls)}] Đang xử lý: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                soup = BeautifulSoup(await page.content(), 'html.parser')
                doc_record = {"url": url, "title_web": "", "raw_text": ""}
                
                title_tag = soup.find('h1') or soup.find('title')
                if title_tag: doc_record["title_web"] = title_tag.get_text(strip=True)

                tv = soup.find(id="toan-van")
                if tv: doc_record["raw_text"] = tv.get_text(separator='\n', strip=True)
                
                tbl = soup.find('table', class_='table-striped')
                if tbl:
                    for row in tbl.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            lbl = cells[0].get_text(strip=True).replace(':', '')
                            val_anchor = cells[1].find('a')
                            val = val_anchor.get_text(strip=True) if val_anchor else cells[1].get_text(strip=True)
                            doc_record[lbl] = val
                
                if doc_record.get("raw_text"):
                    results.append(doc_record)
                    print(f"  [OK] Thanh cong: {doc_record.get('Số hiệu') or doc_record.get('title_web')}")
            except Exception as e:
                print(f"  ! Lỗi {url}: {e}")
        
        if results:
            output_file = output_dir / "vanbanphapluat_special_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n[DONE] Da luu {len(results)} van ban vao: {output_file}")
            
if __name__ == "__main__":
    asyncio.run(scrape_vanbanphapluat(max_pages=1))

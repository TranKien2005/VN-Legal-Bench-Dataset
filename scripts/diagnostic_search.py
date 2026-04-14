import sys
import io
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from scrapers.luatvietnam_engine import LuatVietnamEngine

def diagnostic():
    engine = LuatVietnamEngine()
    kw = "tranh chấp ly hôn"
    params = {
        "SearchKeyword": kw,
        "Page": 1
    }
    print(f"[*] Testing keyword: '{kw}'")
    results = engine.scrape_search_page(params)
    if not results:
        print("[-] No results found.")
        return
    
    for i, res in enumerate(results):
        title = res["title"]
        match = kw.lower() in title.lower()
        print(f"[{i+1}] Match: {match} | Title: {title}")

if __name__ == "__main__":
    diagnostic()

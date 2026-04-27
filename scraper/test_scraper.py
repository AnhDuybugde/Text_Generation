"""Test nhanh scraper voi selectors da sua."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from scraper import WebnovelScraper

scraper = WebnovelScraper()

# Test fetch 1 chuong free
print("=" * 50)
print("TEST 1: Fetch chuong 1 (free)")
print("=" * 50)

url = "https://webnovel.vn/ai-bao-han-tu-tien/chuong-1/"
html = scraper._fetch_page(url)

if html:
    print(f"[OK] Fetch thanh cong! HTML: {len(html):,} bytes")
    content, title = scraper._extract_chapter_content(html)
    if content:
        print(f"[OK] Tieu de: {title}")
        print(f"[OK] Noi dung: {len(content):,} ky tu")
        print(f"\n--- 300 ky tu dau ---")
        # Only print ASCII-safe
        print(content[:300])
        print(f"\n[OK] Paywall: {'CO' if scraper._is_paywall(html) else 'KHONG'}")
    else:
        print("[FAIL] Khong trich xuat duoc noi dung!")
else:
    print("[FAIL] Khong fetch duoc trang!")

# Test chuong 50 (co the paywall)
print(f"\n{'=' * 50}")
print("TEST 2: Fetch chuong 50 (kiem tra paywall)")
print("=" * 50)

import time
time.sleep(2)
url2 = "https://webnovel.vn/ai-bao-han-tu-tien/chuong-50/"
html2 = scraper._fetch_page(url2)
if html2:
    is_locked = scraper._is_paywall(html2)
    print(f"[INFO] Paywall: {'CO' if is_locked else 'KHONG'}")
    if not is_locked:
        content2, title2 = scraper._extract_chapter_content(html2)
        print(f"[INFO] Tieu de: {title2}")
        print(f"[INFO] Noi dung: {len(content2):,} ky tu")
else:
    print("[INFO] 404 hoac khong tai duoc")

print("\n[DONE] Test hoan tat!")

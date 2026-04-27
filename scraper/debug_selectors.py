"""Test chi tiet selector de debug."""
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

# Test chuong 1 (free)
url = "https://webnovel.vn/ai-bao-han-tu-tien/chuong-1/"
resp = scraper.get(url, timeout=30)
html = resp.text

soup = BeautifulSoup(html, 'lxml')

# Tim tat ca class co chua "content" or "chapter" or "reading"
print("=== TIM CSS CLASSES LIEN QUAN ===")
for tag in soup.find_all(True):
    classes = tag.get('class', [])
    for c in classes:
        if any(kw in c.lower() for kw in ['content', 'chapter', 'reading', 'detail', 'text', 'body']):
            # Dem so p con
            p_count = len(tag.find_all('p', recursive=False))
            text_len = len(tag.get_text())
            print(f"  <{tag.name}> class='{c}' | {p_count} <p> tags | {text_len} chars text")

print("\n=== THU .content-inner ===")
ci = soup.select_one('.content-inner')
if ci:
    ps = ci.find_all('p')
    print(f"  Found .content-inner: {len(ps)} <p> tags")
    for i, p in enumerate(ps[:3]):
        print(f"  p[{i}]: {p.get_text()[:100]}")
else:
    print("  KHONG TIM THAY .content-inner")

print("\n=== THU .chapter-c-content ===")
cc = soup.select_one('.chapter-c-content')
if cc:
    ps = cc.find_all('p')
    print(f"  Found .chapter-c-content: {len(ps)} <p> tags")
    for i, p in enumerate(ps[:3]):
        print(f"  p[{i}]: {p.get_text()[:100]}")
else:
    print("  KHONG TIM THAY .chapter-c-content")

print("\n=== LUU HTML DE KIEM TRA ===")
with open("scraper/debug_chapter1.html", "w", encoding="utf-8") as f:
    f.write(html)
print("  Da luu vao scraper/debug_chapter1.html")

# Test chuong 50 (co the paywall)
print("\n=== TEST CHUONG 50 ===")
url2 = "https://webnovel.vn/ai-bao-han-tu-tien/chuong-50/"
resp2 = scraper.get(url2, timeout=30)
html2 = resp2.text

with open("scraper/debug_chapter50.html", "w", encoding="utf-8") as f:
    f.write(html2)
print("  Da luu vao scraper/debug_chapter50.html")

soup2 = BeautifulSoup(html2, 'lxml')
ci2 = soup2.select_one('.content-inner')
if ci2:
    ps2 = ci2.find_all('p')
    print(f"  .content-inner: {len(ps2)} <p> tags")
    for i, p in enumerate(ps2[:3]):
        print(f"  p[{i}]: {p.get_text()[:100]}")
else:
    print("  KHONG TIM THAY .content-inner")
    
# Check for paywall signs
page_text = soup2.get_text()
paywall_signs = ['unlock', 'dang-nhap', 'nap-xu', 'mua-chuong']
for sign in paywall_signs:
    if sign in html2.lower():
        print(f"  Paywall sign found: {sign}")
        
if 'login' in html2.lower() or 'dang-nhap' in html2.lower():
    print("  Login/DangNhap found in HTML")

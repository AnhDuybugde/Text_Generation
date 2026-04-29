import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import sys

base_urls = [
    "https://truyenfull.vision/danh-sach/tien-hiep-hay",
    "https://truyenfull.vision/danh-sach/kiem-hiep-hay",
    "https://truyenfull.vision/the-loai/tien-hiep",
    "https://truyenfull.vision/the-loai/kiem-hiep"
]

scraper = cloudscraper.create_scraper()
slugs = set()

MAX_PAGES = 100  # Quét tối đa 100 trang để gom sạch dữ liệu
for base_url in base_urls:
    for page in range(1, MAX_PAGES + 1):
        url = f"{base_url}/trang-{page}/" if page > 1 else f"{base_url}/"
        print(f"Fetching {url}... ", end="")
        try:
            resp = scraper.get(url, timeout=15, allow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                titles = soup.select('.truyen-title a')
                
                if not titles:
                    print(f"No more novels found on page {page}. Stopping.")
                    break
                    
                count = 0
                for t in titles:
                    link = t.get('href', '')
                    if link:
                        path = urlparse(link).path
                        slug = path.strip('/')
                        if slug:
                            slugs.add(slug)
                            count += 1
                print(f"Found {count} slugs.")
            elif resp.status_code == 404:
                print("404 Not Found. Reached end of category.")
                break
            else:
                print(f"HTTP {resp.status_code}")
                break
        except Exception as e:
            print(f"Error: {e}")
            break

if slugs:
    existing = set()
    try:
        with open('scraper/novel_list_tf.txt', 'r', encoding='utf-8') as f:
            existing = {line.strip() for line in f if line.strip() and not line.startswith('#')}
    except FileNotFoundError:
        pass
        
    new_slugs = slugs - existing
    with open('scraper/novel_list_tf.txt', 'a', encoding='utf-8') as f:
        # Tách comment header cho mục mới
        f.write("\n# === TỰ ĐỘNG CÀO TỪ DANH MỤC TRUYENFULL ===\n")
        count = 0
        for s in sorted(new_slugs):
            f.write(s + '\n')
            count += 1
    print(f"\n=> Đã bổ sung thành công {count} truyện mới vào scraper/novel_list_tf.txt!")
else:
    print("\n=> Không tìm thấy truyện nào.")

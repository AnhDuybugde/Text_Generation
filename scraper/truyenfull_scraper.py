import os
import re
import json
import time
import random
import threading
import unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import cloudscraper
from bs4 import BeautifulSoup

# ============ CONFIG ============
BASE_URL = "https://truyenfull.vision"
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
PROGRESS_FILE = Path(__file__).parent / "progress_tf.json"
NOVEL_LIST_FILE = Path(__file__).parent / "novel_list_tf.txt"

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
]

# Rate limiting
MIN_DELAY = 1.0  # giây
MAX_DELAY = 3.0  # giây
MAX_CONSECUTIVE_FAILS = 3
MAX_CHAPTERS_PER_NOVEL = 5000 # Truyenfull có những truyện cực dài

class TruyenFullScraper:
    def __init__(self):
        self.progress = self._load_progress()
        self.stats = {
            'total_novels': 0,
            'total_chapters': 0,
            'total_chars': 0,
            'failed_novels': [],
        }
        self.lock = threading.Lock()

    def _load_progress(self):
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'completed_novels': [], 'partial': {}}

    def _save_progress(self):
        with self.lock:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def _delay(self):
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    def _fetch_page(self, scraper, url, retries=3):
        for attempt in range(retries):
            try:
                resp = scraper.get(url, timeout=30, allow_redirects=True)
                
                # Check cho việc TruyenFull redirect về trang chủ/list chapter khi quá số lượng chương
                if url.split('/')[-2] not in resp.url and 'chuong-' not in resp.url:
                    return None, True # Báo hiệu bị redirect do hết chương
                
                if resp.status_code == 200:
                    return resp.text, False
                elif resp.status_code == 404:
                    return None, True
                elif resp.status_code in [403, 429, 503]:
                    print(f"  [!] Bị block/giới hạn (HTTP {resp.status_code}) - Cố gắng né tránh màng lọc... Đợi {(attempt+1)*5}s")
                    time.sleep((attempt + 1) * 5)
                else:
                    print(f"  [!] HTTP {resp.status_code} cho {url}")
                    time.sleep(5)
            except Exception as e:
                print(f"  [!] Lỗi mang khi fetch {url}: {e}")
                time.sleep((attempt + 1) * 5)
        return None, False

    def _clean_text(self, text):
        text = unicodedata.normalize('NFC', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _extract_chapter_content(self, html):
        soup = BeautifulSoup(html, 'lxml')

        # Lấy tiêu đề chương
        title_el = soup.find(class_='chapter-title')
        chapter_title = title_el.get_text(strip=True) if title_el else ""

        # Lấy nội dung chương
        content_el = soup.find(class_='chapter-c')
        if not content_el:
            return None, chapter_title

        # Xóa script hoặc div rác nếu có
        for script in content_el.find_all('script'):
            script.decompose()

        # Thay thẻ break bằng xuống dòng
        for br in content_el.find_all('br'):
            br.replace_with('\n')

        # Xử lý thẻ p
        content = content_el.get_text('\n')
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = self._clean_text(content)
        
        return content, chapter_title

    def scrape_novel(self, slug):
        if slug in self.progress['completed_novels']:
            print(f"  [✓] Đã cào trước đó, bỏ qua: {slug}")
            return

        novel_dir = DATA_DIR / slug
        novel_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  Đang cào (TruyenFull): {slug}")
        print(f"{'='*60}")

        # KHỞI TẠO SCRAPER ĐỘC LẬP CHO TỪNG TRUYỆN / TỪNG LUỒNG KÈM THEO TRỘN USER-AGENT
        # Để dẽ dàng né Cloudflare / WAF
        local_scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        local_scraper.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': BASE_URL,
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1'
        })

        start_chapter = self.progress.get('partial', {}).get(slug, 1)
        consecutive_fails = 0
        chapters_scraped = 0

        for chapter_num in range(start_chapter, MAX_CHAPTERS_PER_NOVEL + 1):
            url = f"{BASE_URL}/{slug}/chuong-{chapter_num}/"
            html, redirected = self._fetch_page(local_scraper, url)

            # Trường hợp TruyenFull redirect về #list-chapter
            if redirected or html is None:
                print(f"  => {slug}: Vượt quá số chương hiện có (Chương {chapter_num}). Đã hoàn thành.")
                break

            content, chapter_title = self._extract_chapter_content(html)

            if content and len(content) > 50:
                filename = f"chuong_{chapter_num:04d}.txt"
                filepath = novel_dir / filename
                full_content = f"{chapter_title}\n\n{content}" if chapter_title else content
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(full_content)

                chapters_scraped += 1
                consecutive_fails = 0
                char_count = len(content)
                
                with self.lock:
                    self.stats['total_chars'] += char_count

                title_short = chapter_title[:40] + "..." if len(chapter_title) > 40 else chapter_title
                print(f"  [✓] {slug} - C{chapter_num}: {title_short} ({char_count:,} ký tự)")
            else:
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    break

            with self.lock:
                self.progress['partial'][slug] = chapter_num + 1
            self._save_progress()
            self._delay()

        with self.lock:
            self.progress['completed_novels'].append(slug)
            if slug in self.progress.get('partial', {}):
                del self.progress['partial'][slug]
            self.stats['total_novels'] += 1
            self.stats['total_chapters'] += chapters_scraped
            
            if chapters_scraped == 0:
                self.stats['failed_novels'].append(slug)
                
        self._save_progress()
        print(f"  => Hoàn thành {slug}: {chapters_scraped} chương")

    def run(self):
        if not NOVEL_LIST_FILE.exists():
            print(f"[!] Không tìm thấy {NOVEL_LIST_FILE}.")
            return
            
        with open(NOVEL_LIST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        slugs = []
        seen = set()
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and line not in seen:
                slugs.append(line)
                seen.add(line)

        print(f"\n{'#'*60}")
        print(f"  TRUYENFULL.VISION SCRAPER (ĐA LUỒNG + BYPASS CLOUDFLARE)")
        print(f"  Số truyện: {len(slugs)}")
        print(f"  Luồng đồng thời (Mức Cực Đại): 15")
        print(f"  Lưu vào: {DATA_DIR}")
        print(f"{'#'*60}\n")

        # Tăng số luồng lên 15 cho tốc độ chớp nhoáng
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(self.scrape_novel, slug): slug for slug in slugs}
            for future in as_completed(futures):
                slug = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"  [ERROR] Lỗi khi cào {slug}: {e}")
                    with self.lock:
                        self.stats['failed_novels'].append(slug)

        self._print_stats()

    def _print_stats(self):
        print(f"\n{'='*60}")
        print(f"  THỐNG KÊ TỔNG KẾT TRUYENFULL")
        print(f"{'='*60}")
        print(f"  Tổng truyện đã cào: {self.stats['total_novels']}")
        print(f"  Tổng chương đã lưu: {self.stats['total_chapters']}")
        print(f"  Tổng ký tự: {self.stats['total_chars']:,}")
        if self.stats['failed_novels']:
            print(f"  Truyện lỗi: {', '.join(self.stats['failed_novels'])}")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    scraper = TruyenFullScraper()
    scraper.run()

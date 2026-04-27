"""
Webnovel.vn Scraper - Thu thập dữ liệu truyện Tiên Hiệp / Kiếm Hiệp
Chỉ cào các chương miễn phí, dùng cho mục đích học tập cá nhân.
"""

import os
import re
import json
import time
import random
import unicodedata
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup
from tqdm import tqdm

# ============ CONFIG ============
BASE_URL = "https://webnovel.vn"
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
PROGRESS_FILE = Path(__file__).parent / "progress.json"
NOVEL_LIST_FILE = Path(__file__).parent / "novel_list.txt"

# Rate limiting
MIN_DELAY = 2.0  # giây
MAX_DELAY = 4.0  # giây

# Giới hạn
MAX_CHAPTERS_PER_NOVEL = 80   # Tối đa thử bao nhiêu chương
MAX_CONSECUTIVE_FAILS = 3     # Dừng sau N chương liên tiếp không có nội dung

# ============ SCRAPER CLASS ============

class WebnovelScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.scraper.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': BASE_URL,
        })
        self.progress = self._load_progress()
        self.stats = {
            'total_novels': 0,
            'total_chapters': 0,
            'total_chars': 0,
            'failed_novels': [],
        }

    def _load_progress(self):
        """Load tiến trình đã lưu (để resume nếu bị gián đoạn)."""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'completed_novels': [], 'partial': {}}

    def _save_progress(self):
        """Lưu tiến trình hiện tại."""
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def _delay(self):
        """Random delay để tránh bị block."""
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    def _fetch_page(self, url, retries=3):
        """Fetch một trang với retry logic."""
        for attempt in range(retries):
            try:
                resp = self.scraper.get(url, timeout=30)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 404:
                    return None
                elif resp.status_code == 403:
                    print(f"  [!] 403 Forbidden - có thể bị Cloudflare block. Đợi lâu hơn...")
                    time.sleep(10 + attempt * 5)
                else:
                    print(f"  [!] HTTP {resp.status_code} cho {url}")
                    time.sleep(5)
            except Exception as e:
                print(f"  [!] Lỗi khi fetch {url}: {e}")
                time.sleep(5)
        return None

    def _clean_text(self, text):
        """Làm sạch text đã trích xuất."""
        # Chuẩn hóa Unicode NFC
        text = unicodedata.normalize('NFC', text)
        # Xóa khoảng trắng thừa
        text = re.sub(r'[ \t]+', ' ', text)
        # Xóa dòng trống liên tiếp
        text = re.sub(r'\n{3,}', '\n\n', text)
        # trim
        text = text.strip()
        return text

    def _extract_chapter_content(self, html):
        """Trích xuất nội dung chương từ HTML."""
        soup = BeautifulSoup(html, 'lxml')

        # Lấy tiêu đề chương - selector: p.reader__chapter
        title_el = soup.select_one('p.reader__chapter')
        chapter_title = title_el.get_text(strip=True) if title_el else ""

        # Lấy nội dung chương - selector: div#chapter-c
        content_el = soup.select_one('div#chapter-c')
        if not content_el:
            # Fallback: article.reader__content
            content_el = soup.select_one('article.reader__content')

        if not content_el:
            return None, chapter_title

        # Xóa các quảng cáo xen trong nội dung (Google Adsense)
        for ad in content_el.find_all('ins', class_='adsbygoogle'):
            ad.decompose()
        for ad in content_el.find_all('div', style=lambda s: s and 'text-align:center' in s):
            ad.decompose()
        for script in content_el.find_all('script'):
            script.decompose()

        # Content dùng <br><br> thay vì <p>, cần xử lý đặc biệt
        # Thay thế <br> bằng newline trước khi lấy text
        for br in content_el.find_all('br'):
            br.replace_with('\n')

        content = content_el.get_text()

        # Chuẩn hóa: gộp nhiều dòng trống liên tiếp thành 1
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = self._clean_text(content)
        return content, chapter_title

    def _is_paywall(self, html):
        """Kiểm tra xem chương có bị khóa (paywall) không."""
        if not html:
            return True
        soup = BeautifulSoup(html, 'lxml')

        # Kiểm tra nhanh: nếu không có div#chapter-c => paywall
        content_el = soup.select_one('div#chapter-c')
        if not content_el:
            return True

        # Tìm các dấu hiệu paywall
        paywall_indicators = [
            'Đăng nhập để đọc ngay',
            'Mở khóa chương',
            'unlock-chapter',
            'Vui lòng đăng nhập',
            'Nạp xu để đọc',
        ]
        page_text = soup.get_text()
        # Kiểm tra: nếu có paywall indicator VÀ nội dung rất ngắn
        content, _ = self._extract_chapter_content(html)
        if content and len(content) > 200:
            return False  # Có nội dung dài > 200 ký tự => không phải paywall
        for indicator in paywall_indicators:
            if indicator in page_text:
                return True
        # Nếu nội dung quá ngắn hoặc trống
        if not content or len(content) < 50:
            return True
        return False

    def _get_novel_metadata(self, slug):
        """Lấy metadata về truyện (tên, tác giả, thể loại)."""
        url = f"{BASE_URL}/{slug}/"
        html = self._fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        # Lấy title từ thẻ og:title hoặc title
        title = ""
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '').replace(' - Webnovel.vn', '').strip()
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().split(' - ')[0].strip()

        # Tìm tác giả
        author = ""
        author_link = soup.select_one('a[href*="/tac-gia/"]')
        if author_link:
            author = author_link.get_text(strip=True)

        # Tìm thể loại
        genres = []
        genre_links = soup.select('a[href*="/tien-hiep"], a[href*="/kiem-hiep"], a[href*="/huyen-huyen"], a[href*="/xuyen-khong"], a[href*="/trong-sinh"]')
        for gl in genre_links:
            g = gl.get_text(strip=True)
            if g and g not in genres:
                genres.append(g)

        return {
            'title': title or slug,
            'author': author,
            'genres': genres,
            'slug': slug,
            'url': url,
        }

    def scrape_novel(self, slug):
        """Cào toàn bộ chương miễn phí của một truyện."""
        # Kiểm tra đã hoàn thành chưa
        if slug in self.progress['completed_novels']:
            print(f"  [✓] Đã cào trước đó, bỏ qua: {slug}")
            return

        novel_dir = DATA_DIR / slug
        novel_dir.mkdir(parents=True, exist_ok=True)

        # Lấy metadata
        print(f"\n{'='*60}")
        print(f"  Đang cào: {slug}")
        print(f"{'='*60}")

        metadata = self._get_novel_metadata(slug)
        if metadata:
            with open(novel_dir / 'metadata.json', 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"  Tên: {metadata.get('title', 'N/A')}")
            print(f"  Tác giả: {metadata.get('author', 'N/A')}")
        self._delay()

        # Xác định chương bắt đầu (resume từ progress nếu có)
        start_chapter = self.progress.get('partial', {}).get(slug, 1)
        consecutive_fails = 0
        chapters_scraped = 0

        for chapter_num in range(start_chapter, MAX_CHAPTERS_PER_NOVEL + 1):
            url = f"{BASE_URL}/{slug}/chuong-{chapter_num}/"
            html = self._fetch_page(url)

            if html is None:
                # 404 hoặc lỗi mạng
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    print(f"  [x] {MAX_CONSECUTIVE_FAILS} chương liên tiếp không tìm thấy. Dừng.")
                    break
                continue

            if self._is_paywall(html):
                print(f"  [$$] Chương {chapter_num}: Paywall - dừng cào truyện này.")
                break

            content, chapter_title = self._extract_chapter_content(html)

            if content and len(content) > 50:
                # Lưu chương
                filename = f"chuong_{chapter_num:04d}.txt"
                filepath = novel_dir / filename
                
                # Thêm header với tiêu đề chương
                full_content = f"{chapter_title}\n\n{content}" if chapter_title else content
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(full_content)

                chapters_scraped += 1
                consecutive_fails = 0
                char_count = len(content)
                self.stats['total_chars'] += char_count

                # Hiển thị tiến trình
                title_short = chapter_title[:40] + "..." if len(chapter_title) > 40 else chapter_title
                print(f"  [✓] Chương {chapter_num}: {title_short} ({char_count:,} ký tự)")
            else:
                consecutive_fails += 1
                print(f"  [!] Chương {chapter_num}: Nội dung trống hoặc quá ngắn")
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    print(f"  [x] {MAX_CONSECUTIVE_FAILS} chương liên tiếp trống. Dừng.")
                    break

            # Cập nhật progress
            self.progress['partial'][slug] = chapter_num + 1
            self._save_progress()
            self._delay()

        # Đánh dấu hoàn thành
        self.progress['completed_novels'].append(slug)
        if slug in self.progress.get('partial', {}):
            del self.progress['partial'][slug]
        self._save_progress()

        self.stats['total_novels'] += 1
        self.stats['total_chapters'] += chapters_scraped
        print(f"  => Hoàn thành {slug}: {chapters_scraped} chương")

        if chapters_scraped == 0:
            self.stats['failed_novels'].append(slug)

    def run(self):
        """Chạy scraper cho toàn bộ danh sách truyện."""
        # Đọc danh sách truyện
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
        print(f"  WEBNOVEL.VN SCRAPER")
        print(f"  Số truyện: {len(slugs)}")
        print(f"  Đã hoàn thành trước đó: {len(self.progress.get('completed_novels', []))}")
        print(f"  Lưu vào: {DATA_DIR}")
        print(f"{'#'*60}\n")

        for i, slug in enumerate(slugs, 1):
            print(f"\n[{i}/{len(slugs)}] ", end="")
            try:
                self.scrape_novel(slug)
            except KeyboardInterrupt:
                print("\n\n[!] Dừng bởi người dùng (Ctrl+C). Tiến trình đã được lưu.")
                self._save_progress()
                break
            except Exception as e:
                print(f"  [ERROR] Lỗi khi cào {slug}: {e}")
                self.stats['failed_novels'].append(slug)
                continue

        # In thống kê cuối
        self._print_stats()

    def _print_stats(self):
        """In thống kê tổng kết."""
        print(f"\n{'='*60}")
        print(f"  THỐNG KÊ TỔNG KẾT")
        print(f"{'='*60}")
        print(f"  Tổng truyện đã cào: {self.stats['total_novels']}")
        print(f"  Tổng chương đã lưu: {self.stats['total_chapters']}")
        print(f"  Tổng ký tự: {self.stats['total_chars']:,}")
        print(f"  Ước tính dung lượng: ~{self.stats['total_chars'] / 1024 / 1024:.1f} MB")
        if self.stats['failed_novels']:
            print(f"  Truyện lỗi: {', '.join(self.stats['failed_novels'])}")
        print(f"{'='*60}\n")


# ============ MAIN ============
if __name__ == '__main__':
    scraper = WebnovelScraper()
    scraper.run()

import re
html = open('temp_test.html', encoding='utf-8').read()
slugs = set(re.findall(r'href="(?:https://webnovel\.vn)?/([^/]+)/"', html))
ignore = ['all', 'truyen-moi-dang', 'truyen-duoc-yeu-thich-nhat', 'truyen-duoc-xem-nhieu-nhat', 'truyen-full', 'tien-hiep', 'kiem-hiep', 'ngon-tinh', 'xuyen-khong', 'trong-sinh', 'dien-van', 'huyen-huyen', 'co-dai', 'hien-dai', 'tong-tai', 'do-thi', 'quan-truong', 'lich-su', 'thap-nien-60-70-80', 'he-thong', 'vong-du', 'tam-linh', 'kinh-doanh', 'phat-trien-ban-than', 'sach-hay', 'tim-kiem', 'topup', 'history', 'tac-gia']
valid = [s for s in slugs if s not in ignore and not s.startswith('assets') and not s.startswith('img')]
print("\n".join(valid[:60]))

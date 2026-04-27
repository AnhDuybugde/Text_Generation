import os
import glob
from pathlib import Path

def build_corpus():
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = processed_dir / "corpus.txt"
    
    chapter_files = glob.glob(str(raw_dir / "**/*.txt"), recursive=True)
    
    print(f"Bắt đầu gộp {len(chapter_files)} file vào {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # Bỏ qua một số line không hợp lệ hoặc footer sót lại nếu có
        for idx, file_path in enumerate(chapter_files):
            with open(file_path, 'r', encoding='utf-8') as infile:
                text = infile.read().strip()
                if len(text) > 50:
                    outfile.write(text + "\n\n")
            if (idx + 1) % 100 == 0:
                print(f"Đã xử lý {idx + 1} file...")
                
    st = os.stat(output_file)
    print(f"Hoàn thành! Kích thước corpus: {st.st_size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    build_corpus()

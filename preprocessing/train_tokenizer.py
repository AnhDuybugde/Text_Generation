import os
from pathlib import Path
from tokenizers import ByteLevelBPETokenizer
from transformers import PreTrainedTokenizerFast

def train_tokenizer():
    corpus_file = "data/processed/corpus.txt"
    output_dir = "models/tokenizer"
    
    print("Bắt đầu train Byte-Level BPE Tokenizer...")
    print(f"Dữ liệu từ: {corpus_file}")
    
    # Khởi tạo Byte-Level BPE tokenizer (giống GPT-2)
    tokenizer = ByteLevelBPETokenizer()
    
    # Bắt đầu train
    tokenizer.train(
        files=[corpus_file],
        vocab_size=32000,
        min_frequency=2,
        special_tokens=[
            "<|endoftext|>" # Token bắt đầu / kết thúc / unknown 
        ]
    )
    
    # Tạo thư mục và lưu tokenizer (format của `tokenizers`)
    os.makedirs(output_dir, exist_ok=True)
    tokenizer.save_model(output_dir)
    print(f"Đã lưu vocab.json và merges.txt tại {output_dir}")
    
    # Đóng gói thành PreTrainedTokenizerFast để dùng dễ dàng với Hugging Face Transformers
    fast_tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer._tokenizer,
        bos_token="<|endoftext|>",
        eos_token="<|endoftext|>",
        unk_token="<|endoftext|>",
        pad_token="<|endoftext|>"
    )
    fast_tokenizer.save_pretrained(output_dir)
    print(f"Đã lưu Hugging Face Tokenizer tại {output_dir}")

if __name__ == '__main__':
    train_tokenizer()

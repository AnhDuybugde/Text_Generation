import torch
from transformers import PreTrainedTokenizerFast
import os

def pack_dataset():
    block_size = 512
    tokenizer_dir = "models/tokenizer"
    corpus_file = "data/processed/corpus.txt"
    output_dir = "data/processed"
    
    print("Load tokenizer...")
    tokenizer = PreTrainedTokenizerFast.from_pretrained(tokenizer_dir)
    
    print("Đọc corpus...")
    with open(corpus_file, "r", encoding="utf-8") as f:
        text = f.read()

    print("Tokenizing... (Sẽ mất khoảng thời gian ngắn)")
    # Encode token. Cần kiểm tra vocab được dùng có bao gồm dấu newline v.v.. hay không
    tokens = tokenizer.encode(text)
    
    print(f"Tổng số tokens: {len(tokens):,}")
    
    # Pack thành các block (Sequence packing)
    # Cắt bỏ phần lẻ không chia hết cho block_size
    num_blocks = len(tokens) // block_size
    packed_tokens = tokens[:num_blocks * block_size]
    
    # Save dưới dạng tensor PyTorch
    tensor_data = torch.tensor(packed_tokens, dtype=torch.long).view(num_blocks, block_size)
    
    out_path = os.path.join(output_dir, "dataset.pt")
    torch.save(tensor_data, out_path)
    print(f"Đã lưu dataset thành: {out_path}")
    print(f"Shape: {tensor_data.shape} ({num_blocks:,} sequence với len {block_size})")

if __name__ == "__main__":
    pack_dataset()

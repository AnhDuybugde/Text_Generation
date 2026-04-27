import os
import math
import time
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import PreTrainedTokenizerFast, GPT2Config, GPT2LMHeadModel
from transformers import get_cosine_schedule_with_warmup
from torch.optim import AdamW

# ==========================================
# CẤU HÌNH HUẤN LUYỆN
# ==========================================
DATA_PATH = "data/processed/dataset.pt"
TOKENIZER_PATH = "models/tokenizer"

# Trên Colab, đổi thành Output dir trong Drive của bạn để không mất checkpoint, vd: "/content/drive/MyDrive/checkpoints"
OUTPUT_DIR = "models/checkpoints" 

EPOCHS = 10
BATCH_SIZE = 8
GRADIENT_ACCUMULATION_STEPS = 4  # Tương đương Batch size thực = 32
LEARNING_RATE = 6e-4
MAX_GRAD_NORM = 1.0
# ==========================================

class NovelDataset(Dataset):
    """Load dataset từ file Torch Tensor đóng gói sẵn"""
    def __init__(self, data_path):
        self.data = torch.load(data_path) # Shape: [N, seq_len]
        
    def __len__(self):
        return self.data.size(0)
        
    def __getitem__(self, idx):
        return self.data[idx]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Thiết bị sử dụng: {device.upper()}")
    
    # 1. Load Data
    print("[*] Đang load dữ liệu...")
    dataset = NovelDataset(DATA_PATH)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, pin_memory=True)
    print(f"    Tổng số sequence: {len(dataset)}")
    print(f"    Tổng số batch mỗi epoch (bs={BATCH_SIZE}): {len(dataloader)}")
    
    # 2. Xây dựng Kiến trúc Mô hình
    print("[*] Khởi tạo Tokenizer và Mô hình...")
    tokenizer = PreTrainedTokenizerFast.from_pretrained(TOKENIZER_PATH)
    # Tối ưu vocab size lên bội số của 64 để hỗ trợ Tensor Core trên GPU T4 tốt hơn
    vocab_size = math.ceil(tokenizer.vocab_size / 64) * 64 

    # GPT-2 Small config (124M tham số) nhưng tuỳ chỉnh vocab_size và sequence length 
    config = GPT2Config(
        vocab_size=vocab_size,
        n_positions=512, # Khớp với block_size trong pack_dataset.py
        n_embd=768,
        n_layer=12,
        n_head=12,
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
    )
    
    # Khởi tạo mô hình MỚI HOÀN TOÀN (from scratch), không truyền pre-trained weights
    model = GPT2LMHeadModel(config)
    model.to(device)
    
    num_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"    Số lượng tham số mô hình: {num_params:.2f} Triệu")
    
    # 3. Setup Optimizer & Scheduler
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.1)
    
    total_steps = EPOCHS * (len(dataloader) // GRADIENT_ACCUMULATION_STEPS)
    warmup_steps = int(0.05 * total_steps) # 5% số steps dùng để warmup
    
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, 
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps
    )
    
    # Dùng Mixed Precision để train nhanh hơn trên GPU
    scaler = torch.cuda.amp.GradScaler(enabled=(device == 'cuda'))
    
    # 4. Vòng lặp Huấn luyện (Training Loop)
    print("[*] BẮT ĐẦU HUẤN LUYỆN")
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        start_time = time.time()
        
        for step, batch in enumerate(dataloader):
            # Input sequences
            x = batch.to(device)
            # Với causal language modeling, labels là đầu vào dịch đi 1 bước. 
            # HuggingFace GPT2LMHeadModel tự động dịch chuyển nếu ta gán labels=x
            
            with torch.autocast(device_type="cuda" if device=="cuda" else "cpu", dtype=torch.float16, enabled=(device=='cuda')):
                outputs = model(input_ids=x, labels=x)
                # Chia loss cho accumulation steps
                loss = outputs.loss / GRADIENT_ACCUMULATION_STEPS
            
            scaler.scale(loss).backward()
            
            # Gradient accumulation
            if (step + 1) % GRADIENT_ACCUMULATION_STEPS == 0 or (step + 1) == len(dataloader):
                # Unscale để clip gradient norm tránh bùng nổ gradient
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
                
                scaler.step(optimizer)
                scaler.update()
                
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                
            total_loss += loss.item() * GRADIENT_ACCUMULATION_STEPS
            
            # In progress
            if step % 50 == 0:
                print(f"    Epoch {epoch+1}/{EPOCHS} | Step {step}/{len(dataloader)} | Loss: {loss.item() * GRADIENT_ACCUMULATION_STEPS:.4f}")
        
        # Thống kê Epoch
        avg_loss = total_loss / len(dataloader)
        epoch_time = time.time() - start_time
        print(f"-> Epoch {epoch+1} hoàn tất | Loss: {avg_loss:.4f} | Thời gian: {epoch_time:.2f}s")
        
        # Lưu Checkpoint mỗi Epoch
        checkpoint_path = os.path.join(OUTPUT_DIR, f"gpt2-epoch-{epoch+1}")
        model.save_pretrained(checkpoint_path)
        tokenizer.save_pretrained(checkpoint_path)
        print(f"    [Lưu] Đã lưu mô hình tại: {checkpoint_path}")

    print("[*] HOÀN TẤT HUẤN LUYỆN.")

if __name__ == "__main__":
    main()

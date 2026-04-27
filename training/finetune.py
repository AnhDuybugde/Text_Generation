import os
import sys
import io

# Cố định encoding UTF-8 để khắc phục lỗi Crash (UnicodeEncodeError) trên màn hình CMD/Powershell của Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from transformers import (
    GPT2LMHeadModel,
    GPT2Tokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments
)
import torch
from torch.utils.data import Dataset

# ==========================================
# CẤU HÌNH FINE-TUNING ĐỂ CHẠY TRÊN COLAB
# ==========================================
# Sử dụng pre-trained model Tiếng Việt của ĐH Bách Khoa
MODEL_NAME = "NlpHUST/gpt2-vietnamese"  
DATA_PATH = "data/processed/corpus.txt"

# Nếu chạy trên Colab, đổi thành Output dir trong Drive, vd: "/content/drive/MyDrive/finetuned_checkpoint"
OUTPUT_DIR = "models/finetuned_checkpoint" 

EPOCHS = 5
BATCH_SIZE = 8
GRADIENT_ACCUMULATION = 4
LEARNING_RATE = 5e-5 # Learning rate thường nhỏ hơn nhiều khi Fine-Tune so với Train from scratch
# ==========================================

class CustomTextDataset(Dataset):
    def __init__(self, file_path, tokenizer, block_size=512):
        print("    [Dataset] Đang tokenizing toàn bộ text...")
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            
        tokens = tokenizer.encode(text)
        self.examples = []
        for i in range(0, len(tokens) - block_size + 1, block_size):
            self.examples.append(torch.tensor(tokens[i:i + block_size], dtype=torch.long))
        print(f"    [Dataset] Đã đóng gói được {len(self.examples)} block.")
        
    def __len__(self):
        return len(self.examples)
        
    def __getitem__(self, idx):
        return self.examples[idx]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"[*] Đang tải Tokenizer pre-trained từ '{MODEL_NAME}'...")
    tokenizer = GPT2Tokenizer.from_pretrained(MODEL_NAME)
    
    print(f"[*] Đang tải mô hình NLP Tiếng Việt '{MODEL_NAME}'...")
    model = GPT2LMHeadModel.from_pretrained(MODEL_NAME)
    
    print("[*] Chuẩn bị đóng gói Corpus (Quá trình này băm nhỏ corpus.txt thành chunks)...")
    dataset = CustomTextDataset(
        file_path=DATA_PATH,
        tokenizer=tokenizer,
        block_size=512
    )
    
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, 
        mlm=False # GPT-2 là Causal Language Modeling, không phải Masked (như BERT)
    )
    
    # Cấu hình huấn luyện bằng API mạnh mẽ của Hugging Face
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        learning_rate=LEARNING_RATE,
        save_steps=200,
        save_total_limit=2, # Chỉ giữ lại tối đa 2 checkpoint gần nhất để tiết kiệm dung lượng Drive
        prediction_loss_only=True,
        fp16=True, # Ép kiểu Mixed Precision giúp train nhanh gấp đôi trên Colab T4
        logging_steps=50,
        warmup_steps=100
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=dataset,
    )
    
    print("[*] BẮT ĐẦU VẬN CÔNG FINE-TUNE!")
    trainer.train()
    
    print(f"\n[*] TU LUYỆN THÀNH CÔNG! Đang lưu mô hình xuống {OUTPUT_DIR}")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("[*] XONG.")

if __name__ == "__main__":
    main()

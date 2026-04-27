import os
from transformers import (
    GPT2LMHeadModel,
    GPT2Tokenizer,
    TextDataset,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments
)

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

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"[*] Đang tải Tokenizer pre-trained từ '{MODEL_NAME}'...")
    tokenizer = GPT2Tokenizer.from_pretrained(MODEL_NAME)
    
    print(f"[*] Đang tải mô hình NLP Tiếng Việt '{MODEL_NAME}'...")
    model = GPT2LMHeadModel.from_pretrained(MODEL_NAME)
    
    print("[*] Chuẩn bị đóng gói Corpus (Quá trình này băm nhỏ corpus.txt thành chunks)...")
    # Sử dụng TextDataset để đọc file text linh hoạt, bỏ qua dataset.pt trước đó (vì tokenizer giờ đã khác)
    dataset = TextDataset(
        tokenizer=tokenizer,
        file_path=DATA_PATH,
        block_size=512
    )
    
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, 
        mlm=False # GPT-2 là Causal Language Modeling, không phải Masked (như BERT)
    )
    
    # Cấu hình huấn luyện bằng API mạnh mẽ của Hugging Face
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        overwrite_output_dir=True,
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

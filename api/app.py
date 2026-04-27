import os
import torch
import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel

warnings.filterwarnings("ignore")

app = FastAPI(title="Vietnamese Novel Generator API", version="1.0.0")

# Cấu hình CORS để cho phép Frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
# Path mặc định sau khi bạn copy checkpoint từ Drive về máy
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "best_checkpoint")
TOKENIZER_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "tokenizer")

# Global variables for caching model load
model = None
tokenizer = None
device = "cuda" if torch.cuda.is_available() else "cpu"

class GenerateRequest(BaseModel):
    prompt: str
    max_length: int = 150
    temperature: float = 0.8
    top_k: int = 40
    top_p: float = 0.9
    repetition_penalty: float = 1.15

class GenerateResponse(BaseModel):
    prompt: str
    generated_text: str
    status: str

@app.on_event("startup")
def load_model():
    global model, tokenizer
    print(f"Loading tokenizer from {TOKENIZER_PATH}...")
    try:
        tokenizer = PreTrainedTokenizerFast.from_pretrained(TOKENIZER_PATH)
        print("Tokenizer loaded successfully.")
    except Exception as e:
        print(f"Warning: Could not load tokenizer. Details: {str(e)}")
    
    print(f"Loading model from {MODEL_PATH}...")
    try:
        model = GPT2LMHeadModel.from_pretrained(MODEL_PATH)
        model.to(device)
        model.eval()
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Warning: Could not load model Checkpoint. (Bạn nhớ copy thư mục gpt2-epoch-... vào đổi tên thành models/best_checkpoint nhé!). Details: {str(e)}")

@app.post("/generate", response_model=GenerateResponse)
async def generate_text(req: GenerateRequest):
    if model is None or tokenizer is None:
        # Fallback dummy response cho việc test giao diện khi model chưa có sẵn / chưa train xong
        import time
        time.sleep(1.5) # Giả lập độ trễ sinh text của AI
        dummy_text = req.prompt + " " + "Ngay lúc đó, bầu trời vỡ nát, sấm sét ầm ầm giáng xuống. Hắn khẽ nheo mắt cười lạnh: 'Chỉ bằng chút đạo hạnh này cũng đòi lấy mạng bản toạ sao?'. Nói xong, một đạo kiếm quang loé lên, cắt đứt sinh cơ của vạn vật... Liền sau đó, đại thế giới như ngừng chuyển động, mọi ánh mắt đều đổ dồn về bóng dáng gầy gò đang đứng ngạo nghễ giữa không trung."
        return GenerateResponse(prompt=req.prompt, generated_text=dummy_text, status="dummy_mode")

    # Xoá khoản trắng thừa
    prompt = req.prompt.strip()
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=req.max_length,
            temperature=req.temperature,
            top_k=req.top_k,
            top_p=req.top_p,
            repetition_penalty=req.repetition_penalty,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
        
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    return GenerateResponse(prompt=prompt, generated_text=generated_text, status="success")

if __name__ == "__main__":
    import uvicorn
    # Chạy server ở máy ảo / local. Thử với port 8000
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

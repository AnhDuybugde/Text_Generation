import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import sys
import io
import torch
import warnings
import tempfile
import base64
import asyncio
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel

# Đường dẫn tới thư mục web frontend
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")

warnings.filterwarnings("ignore")

app = FastAPI(title="Vietnamese Novel Generator API", version="2.0.0")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== CẤU HÌNH =====================
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "finetuned_checkpoint")
TOKENIZER_PATH = MODEL_PATH

# Gemini API Key - đặt trong biến môi trường hoặc điền trực tiếp
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Thư mục tạm cho audio/image
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "temp_media")
os.makedirs(TEMP_DIR, exist_ok=True)
# ====================================================

# Global variables
model = None
tokenizer = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# ===================== MODELS =======================
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

class TTSRequest(BaseModel):
    text: str
    voice: str = "vi-VN-HoaiMyNeural"  # Giọng nữ VN mặc định

class TTSResponse(BaseModel):
    audio_url: str
    status: str

class ImageRequest(BaseModel):
    prompt: str

class ImageResponse(BaseModel):
    image_base64: str
    status: str
    message: str

# ===================== STARTUP =====================
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
        print(f"Warning: Could not load model. Details: {str(e)}")
    
    if GEMINI_API_KEY:
        print("Gemini API Key: Configured ✓")
    else:
        print("Warning: GEMINI_API_KEY not set. Image generation will be disabled.")

# ============== ENDPOINT 1: SINH VĂN BẢN ============
@app.post("/generate", response_model=GenerateResponse)
async def generate_text(req: GenerateRequest):
    if model is None or tokenizer is None:
        import time
        time.sleep(1.5)
        dummy_text = req.prompt + " " + "Ngay lúc đó, bầu trời vỡ nát, sấm sét ầm ầm giáng xuống. Hắn khẽ nheo mắt cười lạnh: 'Chỉ bằng chút đạo hạnh này cũng đòi lấy mạng bản toạ sao?'. Nói xong, một đạo kiếm quang loé lên, cắt đứt sinh cơ của vạn vật."
        return GenerateResponse(prompt=req.prompt, generated_text=dummy_text, status="dummy_mode")

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
    
    # Cắt câu dở dang cuối cùng
    last_punctuation_idx = max(
        generated_text.rfind('.'),
        generated_text.rfind('!'),
        generated_text.rfind('?'),
        generated_text.rfind('"'),
        generated_text.rfind('\u201d')
    )
    
    if last_punctuation_idx != -1 and last_punctuation_idx > len(prompt):
        generated_text = generated_text[:last_punctuation_idx + 1]
    
    return GenerateResponse(prompt=prompt, generated_text=generated_text, status="success")

# ============== ENDPOINT 2: TEXT-TO-SPEECH ============
@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    try:
        import edge_tts
        
        # Tạo file tạm duy nhất
        filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(TEMP_DIR, filename)
        
        # Sinh giọng nói
        communicate = edge_tts.Communicate(req.text, req.voice)
        await communicate.save(filepath)
        
        return TTSResponse(
            audio_url=f"/audio/{filename}",
            status="success"
        )
    except Exception as e:
        return TTSResponse(audio_url="", status=f"error: {str(e)}")

# Endpoint phục vụ file audio
@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    filepath = os.path.join(TEMP_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="audio/mpeg")
    return {"error": "File not found"}

# ============== ENDPOINT 3: SINH ẢNH (GEMINI) ========
@app.post("/generate-image", response_model=ImageResponse)
async def generate_image(req: ImageRequest):
    if not GEMINI_API_KEY:
        return ImageResponse(
            image_base64="",
            status="error",
            message="GEMINI_API_KEY chua duoc cau hinh. Hay dat bien moi truong GEMINI_API_KEY."
        )
    
    try:
        from google import genai
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Tạo prompt minh họa tiểu thuyết
        image_prompt = f"""Create a dramatic, cinematic illustration in Chinese Wuxia/Xianxia fantasy art style for this novel scene:
"{req.prompt}"
Style: Epic fantasy painting, dramatic lighting, mystical atmosphere, vibrant colors, detailed character design with flowing robes and ancient weapons."""

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=image_prompt,
            config=genai.types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )
        
        # Trích xuất ảnh từ response
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_base64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                return ImageResponse(
                    image_base64=img_base64,
                    status="success",
                    message="Anh minh hoa da duoc tao thanh cong!"
                )
        
        return ImageResponse(
            image_base64="",
            status="error",
            message="Gemini khong tra ve anh. Thu lai voi prompt khac."
        )
        
    except Exception as e:
        return ImageResponse(
            image_base64="",
            status="error",
            message=f"Loi khi goi Gemini API: {str(e)}"
        )

# ============== ENDPOINT: DANH SÁCH GIỌNG NÓI ========
@app.get("/voices")
async def list_voices():
    return {
        "voices": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My (Nữ)", "gender": "female"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh (Nam)", "gender": "male"},
        ]
    }

# ============== PHỤC VỤ GIAO DIỆN WEB ================
# Mount thư mục static (css, js)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

# Trang chủ: trả về index.html
@app.get("/", response_class=HTMLResponse)
async def serve_homepage():
    index_path = os.path.join(WEB_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

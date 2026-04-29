import os
import sys
import io

# Fix Windows console encoding for Unicode characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import re
import torch
import warnings
import base64
import uuid
import random

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel

# Đường dẫn tới thư mục web frontend
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")

warnings.filterwarnings("ignore")

app = FastAPI(title="Tiên Đạo Kỷ Nguyên — AI Story Generator", version="3.0.0")

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

# Thư mục tạm cho audio
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "temp_media")
os.makedirs(TEMP_DIR, exist_ok=True)
# ====================================================

# Global variables
model = None
tokenizer = None
device = "cuda" if torch.cuda.is_available() else "cpu"


# ===================== PYDANTIC MODELS =======================

class StoryBlock(BaseModel):
    type: str           # "narration" hoặc "dialogue"
    speaker: str = ""   # Tên nhân vật (chỉ dùng cho dialogue)
    text: str

class StoryScene(BaseModel):
    id: int
    label: str
    blocks: List[StoryBlock]
    image_prompt: str
    mood: str

class StoryRequest(BaseModel):
    prompt: str
    max_length: int = 800
    temperature: float = 0.7
    top_k: int = 50
    top_p: float = 0.92
    repetition_penalty: float = 1.3

class StoryResponse(BaseModel):
    title: str
    full_text: str
    scenes: List[StoryScene]
    status: str

class ImageRequest(BaseModel):
    prompt: str
    mood: str = "dramatic"

class ImageResponse(BaseModel):
    image_base64: str
    status: str
    message: str

class TTSRequest(BaseModel):
    text: str
    voice: str = "vi-VN-HoaiMyNeural"

class TTSResponse(BaseModel):
    audio_url: str
    status: str


# ===================== STARTUP =====================
@app.on_event("startup")
def load_model():
    global model, tokenizer
    print(f"[*] Loading tokenizer from {TOKENIZER_PATH}...")
    try:
        tokenizer = PreTrainedTokenizerFast.from_pretrained(TOKENIZER_PATH)
        print("[✓] Tokenizer loaded successfully.")
    except Exception as e:
        print(f"[!] Could not load tokenizer: {str(e)}")
    
    print(f"[*] Loading model from {MODEL_PATH}...")
    try:
        model = GPT2LMHeadModel.from_pretrained(MODEL_PATH)
        model.to(device)
        model.eval()
        print(f"[✓] Model loaded successfully on {device.upper()}.")
    except Exception as e:
        print(f"[!] Could not load model: {str(e)}")


# ===================== TEXT POST-PROCESSING =====================

def postprocess_raw_text(raw_text: str, prompt: str) -> str:
    """
    Hậu xử lý kết quả sinh văn bản để tạo đoạn văn mạch lạc:
    1. Loại bỏ prompt lặp lại
    2. Cắt câu dở dang cuối cùng
    3. Loại bỏ chuỗi ký tự rác, lặp từ vô nghĩa
    4. Ghép các câu ngắn thành đoạn văn hoàn chỉnh
    """
    text = raw_text.strip()
    
    # 1. Loại bỏ phần prompt khỏi đầu output
    if text.startswith(prompt):
        text = text[len(prompt):].strip()
    
    # 2. Loại bỏ các dòng trùng lặp liên tiếp
    lines = text.split('\n')
    deduped_lines = []
    prev_line = None
    for line in lines:
        stripped = line.strip()
        if stripped and stripped != prev_line:
            deduped_lines.append(stripped)
            prev_line = stripped
    text = '\n'.join(deduped_lines)
    
    # 3. Phát hiện và cắt bỏ đoạn lặp cụm từ
    text = re.sub(r'((?:\S+\s+){2,5}?)\1{2,}', r'\1', text)
    
    # 4. Cắt câu dở dang cuối cùng
    punctuation_chars = ['.', '!', '?', '"', '\u201d', '\u2019']
    last_idx = -1
    for p in punctuation_chars:
        idx = text.rfind(p)
        if idx > last_idx:
            last_idx = idx
    
    if last_idx > 20:
        text = text[:last_idx + 1]
    
    # 5. Dọn dẹp khoảng trắng thừa
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    # 6. Nếu text quá ngắn sau xử lý, trả về nguyên bản
    if len(text) < 30:
        text = raw_text[len(prompt):].strip() if raw_text.startswith(prompt) else raw_text.strip()
    
    return text


# ===================== STORY STRUCTURING =====================

def extract_title(text: str, prompt: str) -> str:
    """Trích xuất hoặc tạo tiêu đề từ prompt/text."""
    # Nếu prompt ngắn, dùng luôn làm title
    if len(prompt) < 40:
        return prompt
    # Lấy câu đầu tiên
    first_sentence = re.split(r'[.!?。]', prompt)[0].strip()
    if len(first_sentence) > 50:
        first_sentence = first_sentence[:50] + "..."
    return first_sentence


def parse_blocks(text: str) -> List[dict]:
    """
    Phân tích text thành danh sách block narration/dialogue.
    
    Nhận diện dialogue qua:
    - Dấu ngoặc kép: "..." hoặc "..."
    - Dấu gạch ngang dẫn lời: — hoặc - (đầu dòng)
    - Pattern: TÊN NHÂN VẬT nói/hỏi/đáp: "..."
    """
    blocks = []
    
    # Regex pattern cho dialogue
    # Pattern 1: "Tên nhân vật" nói/hỏi: "lời thoại"
    # Pattern 2: — Lời thoại (kiểu tiểu thuyết)
    # Pattern 3: "Lời thoại" hoặc "lời thoại"
    
    # Tách text thành các đoạn theo dòng
    paragraphs = re.split(r'\n+', text)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Thử nhận diện dialogue trong paragraph
        remaining = para
        temp_blocks = []
        
        # Tìm tất cả các đoạn hội thoại trong ngoặc kép
        dialogue_pattern = re.compile(
            r'([^\u201c\u201d"]*?)'                  # Phần narration trước
            r'(?:'
            r'(\w[\w\s]{0,15}?)\s*(?:nói|hỏi|đáp|quát|cười|thở dài|lạnh lùng nói|trầm giọng nói|kêu lên|thét|gào)?'  # Tên nhân vật + verb
            r'\s*[:：]\s*'
            r')?'
            r'[\u201c"\u0022](.+?)[\u201d"\u0022]',   # Lời thoại trong ngoặc
            re.DOTALL
        )
        
        matches = list(dialogue_pattern.finditer(remaining))
        
        if matches:
            last_end = 0
            for match in matches:
                # Narration trước dialogue
                pre_text = remaining[last_end:match.start()].strip()
                narration_part = match.group(1).strip() if match.group(1) else ""
                full_pre = (pre_text + " " + narration_part).strip()
                
                if full_pre and len(full_pre) > 5:
                    temp_blocks.append({"type": "narration", "speaker": "", "text": full_pre})
                
                # Dialogue
                speaker = match.group(2).strip() if match.group(2) else ""
                speech = match.group(3).strip()
                if speech:
                    temp_blocks.append({"type": "dialogue", "speaker": speaker, "text": speech})
                
                last_end = match.end()
            
            # Narration sau dialogue cuối
            post_text = remaining[last_end:].strip()
            if post_text and len(post_text) > 5:
                temp_blocks.append({"type": "narration", "speaker": "", "text": post_text})
            
            if temp_blocks:
                blocks.extend(temp_blocks)
                continue
        
        # Kiểm tra dialogue kiểu dash: — hoặc – ở đầu
        dash_match = re.match(r'^[\u2014\u2013\-]\s*(.+)', para)
        if dash_match:
            speech = dash_match.group(1).strip()
            blocks.append({"type": "dialogue", "speaker": "", "text": speech})
            continue
        
        # Không phải dialogue → narration
        blocks.append({"type": "narration", "speaker": "", "text": para})
    
    # Nếu không tìm được block nào, tạo 1 narration block
    if not blocks:
        blocks.append({"type": "narration", "speaker": "", "text": text})
    
    return blocks


def split_into_scenes(text: str, num_scenes: int = 4) -> List[dict]:
    """
    Chia text thành các scene dựa trên nội dung.
    Mỗi scene có: label, blocks (narration/dialogue), image_prompt, mood.
    """
    scene_labels = [
        ("🌅 Khai Mạc", "mysterious, dawn, misty"),
        ("⚡ Phát Triển", "rising tension, dramatic, stormy"),
        ("🔥 Cao Trào", "intense battle, explosive, climactic"),
        ("⚔️ Đỉnh Điểm", "epic confrontation, powerful, fiery"),
        ("🌙 Kết Thúc", "resolution, peaceful, moonlit"),
    ]
    
    moods = ["mysterious", "dramatic", "intense", "epic", "peaceful"]
    
    # Tách text thành câu
    sentences = re.split(r'(?<=[.!?。])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    
    if len(sentences) < num_scenes:
        # Text quá ngắn, tạo 1-2 scene
        all_blocks = parse_blocks(text)
        scenes = [{
            "id": 1,
            "label": scene_labels[0][0],
            "blocks": all_blocks,
            "image_prompt": _create_image_prompt(text[:200], "mysterious"),
            "mood": "mysterious"
        }]
        return scenes
    
    # Chia đều câu vào các scene
    scene_size = max(1, len(sentences) // num_scenes)
    scenes = []
    
    for i in range(num_scenes):
        start = i * scene_size
        end = start + scene_size if i < num_scenes - 1 else len(sentences)
        scene_text = ' '.join(sentences[start:end]).strip()
        
        if not scene_text or len(scene_text) < 20:
            continue
        
        label_idx = min(i, len(scene_labels) - 1)
        label, mood_hint = scene_labels[label_idx]
        mood = moods[min(i, len(moods) - 1)]
        
        blocks = parse_blocks(scene_text)
        
        scenes.append({
            "id": i + 1,
            "label": label,
            "blocks": blocks,
            "image_prompt": _create_image_prompt(scene_text[:200], mood),
            "mood": mood
        })
    
    return scenes


def _create_image_prompt(scene_text: str, mood: str) -> str:
    """Tạo prompt sinh ảnh từ nội dung scene."""
    clean = scene_text.replace('"', '').replace("'", '').replace('/', ' ')[:150]
    
    mood_map = {
        "mysterious": "misty mountains, dawn light, ethereal atmosphere",
        "dramatic": "stormy sky, dramatic lighting, rising tension",
        "intense": "epic battle scene, explosive energy, fiery glow",
        "epic": "massive confrontation, ancient warriors, divine power",
        "peaceful": "moonlit landscape, serene, gentle winds"
    }
    mood_desc = mood_map.get(mood, "dramatic cinematic lighting")
    
    return (
        f"Chinese Wuxia Xianxia fantasy illustration, {mood_desc}. "
        f"Scene: {clean}. "
        f"Style: Epic cinematic painting, detailed character design with flowing robes, "
        f"ancient weapons, vibrant colors, mystical energy effects. "
        f"High quality, 4K, artstation trending."
    )


# ===================== DUMMY DATA =====================

def generate_dummy_story(prompt: str) -> dict:
    """Tạo truyện mẫu khi model chưa load được."""
    dummy_text = (
        f'{prompt}.\n\n'
        'Giữa Vạn Yêu Cốc sương mù mờ mịt, một bóng trắng đứng lặng trên đỉnh vách đá. '
        'Kiếm khí tỏa ra từ người hắn như sương thu, lạnh buốt xương.\n\n'
        'Lục Dương nắm chặt chuôi kiếm, mắt nhìn về phía trước. "Ngươi tưởng ta sợ sao?" — Hắn lạnh lùng nói.\n\n'
        'Bóng đen đối diện cất tiếng cười ghê rợn. Ma Vân Tà từ trong bóng tối bước ra, '
        'áo choàng đen bay phấp phới trong gió lạnh. "Hắn hắn hắn... Lục Dương, ngươi chỉ '
        'là kiến cỏ trước mặt bản tọa!"\n\n'
        'Sấm sét ầm ầm vang lên. Lục Dương rút kiếm, một đạo kiếm quang chói lọi xé toạc '
        'màn đêm. "Thiên Hà Kiếm Quyết — Đệ Tam Thức!" — Hắn hét lớn.\n\n'
        'Kiếm và chưởng va vào nhau, sóng khí bùng nổ ra bốn phía. Cây cối trong bán kính '
        'trăm trượng bị san phẳng. Ma Vân Tà lùi ba bước, máu rỉ từ khóe miệng.\n\n'
        '"Ngươi... ngươi đã đột phá Nguyên Anh Kỳ?!" — Ma Vân Tà kinh hãi thốt lên.\n\n'
        'Lục Dương thu kiếm, ánh mắt bình thản như nước hồ thu. '
        '"Cút đi. Lần sau gặp lại, ta sẽ không nương tay." '
        'Nói xong, hắn quay lưng bước đi, bóng lưng cô độc giữa ánh trăng bạc.'
    )
    return {
        "title": extract_title(dummy_text, prompt),
        "full_text": dummy_text,
        "scenes": split_into_scenes(dummy_text, 4),
        "status": "dummy_mode"
    }


# ===================== ENDPOINT: SINH TRUYỆN =====================

@app.post("/generate-story", response_model=StoryResponse)
async def generate_story(req: StoryRequest):
    """Sinh truyện kiếm hiệp hoàn chỉnh với cấu trúc scene/narration/dialogue."""
    
    if model is None or tokenizer is None:
        import time
        time.sleep(1.5)
        data = generate_dummy_story(req.prompt)
        return StoryResponse(**data)
    
    prompt = req.prompt.strip()
    effective_prompt = prompt if len(prompt) >= 20 else f"{prompt}."
    
    inputs = tokenizer(effective_prompt, return_tensors="pt", truncation=True, max_length=512).to(device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=req.max_length,
            temperature=max(0.3, min(req.temperature, 1.2)),
            top_k=req.top_k,
            top_p=req.top_p,
            repetition_penalty=req.repetition_penalty,
            no_repeat_ngram_size=4,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
        
    raw_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    clean_text = postprocess_raw_text(raw_text, effective_prompt)
    
    title = extract_title(clean_text, prompt)
    scenes = split_into_scenes(clean_text, 4)
    
    return StoryResponse(
        title=title,
        full_text=clean_text,
        scenes=scenes,
        status="success"
    )


# ===================== ENDPOINT: SINH ẢNH =====================

@app.post("/generate-scene-image", response_model=ImageResponse)
async def generate_scene_image(req: ImageRequest):
    """Sinh ảnh minh họa cho một phân cảnh."""
    try:
        import requests
        import urllib.parse
        
        safe_prompt = urllib.parse.quote(req.prompt[:500])
        seed = random.randint(1, 10000)
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=576&nologo=true&seed={seed}"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=60)
        
        if res.status_code == 200:
            img_base64 = base64.b64encode(res.content).decode("utf-8")
            return ImageResponse(
                image_base64=img_base64,
                status="success",
                message="Ảnh minh họa đã được tạo thành công!"
            )
        else:
            raise Exception(f"Pollinations API error: HTTP {res.status_code}")
            
    except Exception as e:
        return ImageResponse(
            image_base64="",
            status="error",
            message=f"Lỗi khi tạo ảnh: {str(e)}"
        )


# ===================== ENDPOINT: TEXT-TO-SPEECH =====================

@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """Chuyển văn bản thành giọng nói tiếng Việt."""
    try:
        import edge_tts
        
        filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(TEMP_DIR, filename)
        
        communicate = edge_tts.Communicate(req.text, req.voice)
        await communicate.save(filepath)
        
        return TTSResponse(audio_url=f"/audio/{filename}", status="success")
    except Exception as e:
        return TTSResponse(audio_url="", status=f"error: {str(e)}")


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    filepath = os.path.join(TEMP_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="audio/mpeg")
    return {"error": "File not found"}


@app.get("/voices")
async def list_voices():
    return {
        "voices": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My (Nữ)", "gender": "female"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh (Nam)", "gender": "male"},
        ]
    }


# ===================== PHỤC VỤ GIAO DIỆN WEB =====================
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_homepage():
    index_path = os.path.join(WEB_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

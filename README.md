# 🐉 Tiên Đạo Kỷ Nguyên — AI Kiếm Hiệp Story Generator

AI-powered Vietnamese Wuxia/Xianxia story generator with scene illustrations, character dialogue, and voiceover.

## Features

- **📝 Script Generation** — GPT-2 fine-tuned on 870MB Vietnamese martial arts novel corpus
- **⚔️ Structured Stories** — Narration & dialogue separated with character attribution
- **🎨 Scene Illustrations** — AI-generated images matching each scene's context
- **🔊 Text-to-Speech** — Vietnamese voiceover with edge-tts
- **📊 Real-time Progress** — Step-by-step progress tracking during generation

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn torch transformers python-dotenv edge-tts requests pydantic

# Run the server
cd api
python app.py

# Open http://localhost:8000
```

## Project Structure

```
Text_Generation/
├── api/app.py                  # FastAPI server (story gen + TTS + image)
├── web/                        # Frontend (HTML/CSS/JS)
├── models/finetuned_checkpoint # GPT-2 Vietnamese fine-tuned model
├── scraper/                    # Data collection scrapers
├── preprocessing/              # Corpus building & tokenizer training
├── training/                   # Model training scripts
├── data/                       # Raw novels + processed corpus
├── docs/                       # Research documents
└── extract_*.py                # Utility scripts for novel discovery
```

## Pipeline

1. **Scrape** → `scraper/webnovel_scraper.py` + `scraper/truyenfull_scraper.py`
2. **Preprocess** → `preprocessing/build_corpus.py` → `train_tokenizer.py` → `pack_dataset.py`
3. **Train** → `training/finetune.py` (fine-tune NlpHUST/gpt2-vietnamese)
4. **Serve** → `api/app.py` → `http://localhost:8000`

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/generate-story` | POST | Generate structured story with scenes, narration & dialogue |
| `/generate-scene-image` | POST | Generate illustration for a scene |
| `/tts` | POST | Text-to-speech conversion |
| `/voices` | GET | List available TTS voices |

## Tech Stack

- **Model:** GPT-2 (NlpHUST/gpt2-vietnamese fine-tuned)
- **Backend:** FastAPI + PyTorch + Transformers
- **Frontend:** Vanilla HTML/CSS/JS, Glassmorphism dark theme
- **TTS:** edge-tts (Microsoft Neural Voices)
- **Images:** Pollinations AI

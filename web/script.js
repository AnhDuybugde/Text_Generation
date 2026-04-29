const API_BASE = "http://localhost:8000";

// ===================== DOM ELEMENTS =====================
const promptInput = document.getElementById("prompt-input");
const generateBtn = document.getElementById("generate-btn");
const loader = document.getElementById("loader");
const tempSlider = document.getElementById("temp-slider");
const tempVal = document.getElementById("temp-val");
const voiceSelect = document.getElementById("voice-select");

const storyPanel = document.getElementById("story-panel");
const storyTitle = document.getElementById("story-title");
const storyContent = document.getElementById("story-content");
const progressTracker = document.getElementById("progress-tracker");
const progressFill = document.getElementById("progress-fill");
const audioContainer = document.getElementById("audio-container");
const audioPlayer = document.getElementById("audio-player");

// Step elements
const STEPS = [
    document.getElementById("step-init"),
    document.getElementById("step-script"),
    document.getElementById("step-parse"),
    document.getElementById("step-img"),
    document.getElementById("step-tts"),
    document.getElementById("step-done"),
];

// State
let isGenerating = false;

// ===================== SLIDER =====================
tempSlider.addEventListener("input", () => {
    tempVal.textContent = tempSlider.value;
});

// ===================== UTILITY =====================
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ===================== PROGRESS =====================
function setProgress(stepIndex, percent) {
    progressFill.style.width = percent + "%";
    
    STEPS.forEach((el, i) => {
        el.classList.remove("active", "done");
        if (i < stepIndex) {
            el.classList.add("done");
        } else if (i === stepIndex) {
            el.classList.add("active");
        }
    });
}

function updateStepLabel(stepIndex, newText) {
    const stepEl = STEPS[stepIndex];
    if (stepEl) {
        const textSpan = stepEl.querySelectorAll("span")[1];
        if (textSpan) textSpan.textContent = newText;
    }
}

// ===================== TYPEWRITER (cho narration) =====================
async function typewriterEffect(text, container) {
    container.textContent = "";
    const chunkSize = 3;
    for (let i = 0; i < text.length; i += chunkSize) {
        container.textContent += text.substring(i, i + chunkSize);
        if (i % 9 === 0) {
            await sleep(6);
        }
    }
}

// ===================== RENDER BLOCKS =====================
async function renderBlocks(blocks, containerEl) {
    for (const block of blocks) {
        if (block.type === "dialogue") {
            // Dialogue block
            const dialogueEl = document.createElement("div");
            dialogueEl.className = "block-dialogue";
            dialogueEl.style.opacity = "0";
            
            if (block.speaker) {
                const speakerEl = document.createElement("div");
                speakerEl.className = "dialogue-speaker";
                speakerEl.textContent = block.speaker;
                dialogueEl.appendChild(speakerEl);
            }
            
            const textEl = document.createElement("div");
            textEl.className = "dialogue-text";
            dialogueEl.appendChild(textEl);
            containerEl.appendChild(dialogueEl);
            
            // Fade in
            dialogueEl.style.transition = "opacity 0.5s ease";
            await sleep(50);
            dialogueEl.style.opacity = "1";
            
            // Typewriter cho dialogue
            await typewriterEffect(block.text, textEl);
            
        } else {
            // Narration block
            const narrationEl = document.createElement("p");
            narrationEl.className = "block-narration";
            containerEl.appendChild(narrationEl);
            
            await typewriterEffect(block.text, narrationEl);
        }
        
        await sleep(100);
    }
}

// ===================== MAIN: TẠO TRUYỆN =====================
generateBtn.addEventListener("click", async () => {
    if (isGenerating) return;
    const prompt = promptInput.value.trim();
    if (!prompt) {
        alert("Xin hãy nhập câu mồi trước khi tạo truyện!");
        return;
    }

    isGenerating = true;
    generateBtn.disabled = true;
    loader.style.display = "inline-block";
    generateBtn.querySelector(".btn-text").textContent = "Đang tạo truyện...";

    // Reset
    storyPanel.style.display = "block";
    storyContent.innerHTML = "";
    storyTitle.style.display = "none";
    audioContainer.style.display = "none";
    progressTracker.style.display = "block";
    
    // Reset step labels
    updateStepLabel(3, "🎨 Đang vẽ minh họa phân cảnh...");
    
    // Cuộn xuống
    storyPanel.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
        // ========== BƯỚC 0: Khởi tạo ==========
        setProgress(0, 5);
        await sleep(400);
        
        // ========== BƯỚC 1: Sinh kịch bản ==========
        setProgress(1, 10);
        
        const storyRes = await fetch(`${API_BASE}/generate-story`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: prompt,
                max_length: 800,
                temperature: parseFloat(tempSlider.value),
            }),
        });
        const storyData = await storyRes.json();
        
        if (!storyData.scenes || storyData.scenes.length === 0) {
            throw new Error("Không thể tạo truyện. Thử lại với prompt khác.");
        }

        // ========== BƯỚC 2: Phân tích ==========
        setProgress(2, 25);
        await sleep(600);
        
        // Hiển thị tiêu đề
        storyTitle.textContent = storyData.title;
        storyTitle.style.display = "block";
        
        const scenes = storyData.scenes;

        // ========== BƯỚC 3: Hiển thị text + sinh ảnh ==========
        setProgress(3, 30);

        for (let i = 0; i < scenes.length; i++) {
            const scene = scenes[i];
            const progressPercent = 30 + ((i + 1) / scenes.length) * 45;

            updateStepLabel(3, `🎨 Đang vẽ phân cảnh ${i + 1}/${scenes.length}...`);

            // Tạo scene container
            const sceneEl = document.createElement("div");
            sceneEl.className = "story-scene";
            sceneEl.style.animationDelay = `${i * 0.1}s`;

            // Scene divider
            const divider = document.createElement("div");
            divider.className = "scene-divider";
            divider.innerHTML = `<span>${scene.label}</span>`;
            sceneEl.appendChild(divider);

            // Blocks container
            const blocksContainer = document.createElement("div");
            blocksContainer.className = "scene-blocks";
            sceneEl.appendChild(blocksContainer);

            // Image wrapper (loading state)
            const imgWrapper = document.createElement("div");
            imgWrapper.className = "scene-image-wrapper loading";
            const imgEl = document.createElement("img");
            imgEl.className = "scene-image";
            imgEl.alt = `Minh họa: ${scene.label}`;
            imgEl.style.display = "none";
            imgWrapper.appendChild(imgEl);
            
            const caption = document.createElement("div");
            caption.className = "scene-image-caption";
            caption.textContent = `Phân cảnh ${i + 1} / ${scenes.length}`;
            
            sceneEl.appendChild(imgWrapper);
            sceneEl.appendChild(caption);
            storyContent.appendChild(sceneEl);

            // Render text blocks với typewriter
            await renderBlocks(scene.blocks, blocksContainer);

            // Sinh ảnh cho scene
            setProgress(3, progressPercent);
            
            try {
                const imgRes = await fetch(`${API_BASE}/generate-scene-image`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        prompt: scene.image_prompt,
                        mood: scene.mood,
                    }),
                });
                const imgData = await imgRes.json();

                if (imgData.status === "success" && imgData.image_base64) {
                    imgEl.src = `data:image/png;base64,${imgData.image_base64}`;
                    imgEl.style.display = "block";
                    imgWrapper.classList.remove("loading");
                } else {
                    imgWrapper.classList.remove("loading");
                    imgWrapper.style.display = "none";
                    caption.textContent = "⚠️ Không thể tạo ảnh cho phân cảnh này";
                }
            } catch (imgErr) {
                console.error("Image error:", imgErr);
                imgWrapper.classList.remove("loading");
                imgWrapper.style.display = "none";
                caption.textContent = "⚠️ Lỗi khi tạo ảnh minh họa";
            }

            // Cuộn tới scene mới
            sceneEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        // ========== BƯỚC 4: TTS ==========
        setProgress(4, 80);

        try {
            // Tạo full text cho TTS (chỉ lấy narration + dialogue text)
            let ttsText = "";
            for (const scene of scenes) {
                for (const block of scene.blocks) {
                    if (block.type === "dialogue" && block.speaker) {
                        ttsText += `${block.speaker} nói: "${block.text}" `;
                    } else {
                        ttsText += block.text + " ";
                    }
                }
            }
            
            const ttsRes = await fetch(`${API_BASE}/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: ttsText.trim(),
                    voice: voiceSelect.value,
                }),
            });
            const ttsData = await ttsRes.json();

            if (ttsData.status === "success") {
                audioPlayer.src = `${API_BASE}${ttsData.audio_url}`;
                audioContainer.style.display = "block";
                audioPlayer.play().catch(e => {
                    console.log("Auto-play blocked:", e);
                });
            }
        } catch (ttsErr) {
            console.error("TTS error:", ttsErr);
        }

        // ========== BƯỚC 5: Hoàn tất ==========
        setProgress(5, 100);
        await sleep(2000);
        progressTracker.style.display = "none";

    } catch (err) {
        storyContent.innerHTML = `<div class="error-message">
            ⚠️ Lỗi: ${err.message}
            <small>Hãy đảm bảo API server đang chạy tại ${API_BASE}</small>
        </div>`;
        progressTracker.style.display = "none";
    } finally {
        isGenerating = false;
        generateBtn.disabled = false;
        loader.style.display = "none";
        generateBtn.querySelector(".btn-text").textContent = "⚔️ Tạo Truyện Hoàn Chỉnh";
    }
});

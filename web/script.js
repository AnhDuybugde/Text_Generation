const API_BASE = "http://localhost:8000";

// ===================== DOM ELEMENTS =====================
const promptInput = document.getElementById("prompt-input");
const generateBtn = document.getElementById("generate-btn");
const outputBox = document.getElementById("output-box");
const loader = document.getElementById("loader");
const tempSlider = document.getElementById("temp-slider");
const tempVal = document.getElementById("temp-val");
const lengthSlider = document.getElementById("length-slider");
const lengthVal = document.getElementById("length-val");

// New elements
const actionToolbar = document.getElementById("action-toolbar");
const ttsBtn = document.getElementById("tts-btn");
const voiceSelect = document.getElementById("voice-select");
const audioContainer = document.getElementById("audio-container");
const audioPlayer = document.getElementById("audio-player");
const imageBtn = document.getElementById("image-btn");
const imageContainer = document.getElementById("image-container");
const generatedImage = document.getElementById("generated-image");

// State
let currentGeneratedText = "";

// ===================== SLIDER EVENTS =====================
tempSlider.addEventListener("input", () => {
    tempVal.textContent = tempSlider.value;
});

lengthSlider.addEventListener("input", () => {
    lengthVal.textContent = lengthSlider.value;
});

// ===================== TYPEWRITER EFFECT =====================
async function typewriterEffect(text, container) {
    container.innerHTML = "";
    const cursor = document.createElement("span");
    cursor.className = "typewriter-cursor";

    for (let i = 0; i < text.length; i++) {
        container.textContent += text[i];
        container.appendChild(cursor);
        // Tốc độ gõ phím ngẫu nhiên tạo cảm giác tự nhiên
        const delay = Math.random() * 20 + 10;
        await new Promise(resolve => setTimeout(resolve, delay));
    }
    // Giữ cursor nhấp nháy ở cuối
    container.appendChild(cursor);
}

// ===================== SINH VĂN BẢN =====================
generateBtn.addEventListener("click", async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
        outputBox.innerHTML = '<p class="placeholder-text">Xin hãy nhập câu mồi trước khi vận công...</p>';
        return;
    }

    // Disable & show loader
    generateBtn.disabled = true;
    loader.style.display = "inline-block";
    generateBtn.querySelector(".btn-text").textContent = "Đang vận công...";
    outputBox.innerHTML = '<p class="placeholder-text">Đang kết nối với thiên đạo...</p>';

    // Ẩn toolbar, audio, image khi sinh mới
    actionToolbar.style.display = "none";
    audioContainer.style.display = "none";
    imageContainer.style.display = "none";

    try {
        const res = await fetch(`${API_BASE}/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: prompt,
                max_length: parseInt(lengthSlider.value),
                temperature: parseFloat(tempSlider.value),
            }),
        });
        const data = await res.json();
        currentGeneratedText = data.generated_text;
        await typewriterEffect(currentGeneratedText, outputBox);

        // Hiện thanh công cụ
        actionToolbar.style.display = "flex";
    } catch (err) {
        outputBox.innerHTML = `<p style="color: #f87171;">⚠️ Lỗi kết nối: ${err.message}. Hãy đảm bảo API server đang chạy tại ${API_BASE}</p>`;
    } finally {
        generateBtn.disabled = false;
        loader.style.display = "none";
        generateBtn.querySelector(".btn-text").textContent = "⚔️ Vận Công Sinh Chữ";
    }
});

// ===================== TEXT-TO-SPEECH =====================
ttsBtn.addEventListener("click", async () => {
    if (!currentGeneratedText) return;

    const originalHTML = ttsBtn.innerHTML;
    ttsBtn.disabled = true;
    ttsBtn.innerHTML = '<span class="mini-loader"></span> Đang tạo giọng...';

    try {
        const res = await fetch(`${API_BASE}/tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: currentGeneratedText,
                voice: voiceSelect.value,
            }),
        });
        const data = await res.json();

        if (data.status === "success") {
            audioPlayer.src = `${API_BASE}${data.audio_url}`;
            audioContainer.style.display = "block";
            audioPlayer.play();
        } else {
            alert("Lỗi TTS: " + data.status);
        }
    } catch (err) {
        alert("Lỗi kết nối TTS: " + err.message);
    } finally {
        ttsBtn.disabled = false;
        ttsBtn.innerHTML = originalHTML;
    }
});

// ===================== SINH ẢNH MINH HỌA =====================
imageBtn.addEventListener("click", async () => {
    if (!currentGeneratedText) return;

    const originalHTML = imageBtn.innerHTML;
    imageBtn.disabled = true;
    imageBtn.innerHTML = '<span class="mini-loader"></span> Đang vẽ...';

    try {
        // Lấy 200 ký tự đầu làm mô tả cảnh
        const sceneDesc = currentGeneratedText.substring(0, 200);

        const res = await fetch(`${API_BASE}/generate-image`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: sceneDesc }),
        });
        const data = await res.json();

        if (data.status === "success" && data.image_base64) {
            generatedImage.src = `data:image/png;base64,${data.image_base64}`;
            imageContainer.style.display = "block";
        } else {
            alert("Lỗi sinh ảnh: " + data.message);
        }
    } catch (err) {
        alert("Lỗi kết nối Image API: " + err.message);
    } finally {
        imageBtn.disabled = false;
        imageBtn.innerHTML = originalHTML;
    }
});

// ===================== PARTICLES ANIMATION =====================
// Tạo hạt bụi tu tiên trôi lững lờ
const particlesContainer = document.getElementById("particles");
// Particles are handled by CSS background animation

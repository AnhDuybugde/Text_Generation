document.addEventListener('DOMContentLoaded', () => {
    const promptInput = document.getElementById('prompt-input');
    const tempSlider = document.getElementById('temp-slider');
    const tempVal = document.getElementById('temp-val');
    const lengthSlider = document.getElementById('length-slider');
    const lengthVal = document.getElementById('length-val');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.querySelector('.btn-text');
    const loader = document.getElementById('loader');
    const outputBox = document.getElementById('output-box');

    // Update slider values
    tempSlider.addEventListener('input', (e) => tempVal.textContent = e.target.value);
    lengthSlider.addEventListener('input', (e) => lengthVal.textContent = e.target.value);

    // Typing Effect Logic
    let typewriterTimeout;
    
    function typeWriter(text, element, speed = 25) {
        clearTimeout(typewriterTimeout);
        element.innerHTML = '';
        
        const textSpan = document.createElement('span');
        const cursorSpan = document.createElement('span');
        cursorSpan.className = 'typewriter-cursor';
        
        element.appendChild(textSpan);
        element.appendChild(cursorSpan);

        let i = 0;
        function type() {
            if (i < text.length) {
                // Xử lý xuống dòng hiển thị đẹp hơn
                if (text.charAt(i) === '\n') {
                    textSpan.appendChild(document.createElement('br'));
                } else {
                    textSpan.appendChild(document.createTextNode(text.charAt(i)));
                }
                i++;
                
                // Randomize slightly for human-like typing speed
                const delay = speed + Math.random() * 20;
                typewriterTimeout = setTimeout(type, delay);
            } else {
                cursorSpan.style.animation = 'blink 1s step-end infinite';
            }
        }
        
        type();
    }

    generateBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) {
            outputBox.innerHTML = '<p class="placeholder-text" style="color: #ff6b6b;">Lão phu cần chút gợi ý (prompt) mới có thể suy diễn thiên cơ...</p>';
            return;
        }

        // Set Loading State
        generateBtn.disabled = true;
        btnText.textContent = 'Đang Suy Diễn...';
        loader.style.display = 'block';
        outputBox.innerHTML = '<p class="placeholder-text">Khí đang tụ đan điền...</p>';

        try {
            // Gọi API local (Chắc chắn uvicorn đang chạy)
            const response = await fetch('http://127.0.0.1:8000/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: prompt,
                    max_length: parseInt(lengthSlider.value),
                    temperature: parseFloat(tempSlider.value),
                    top_k: 40,
                    top_p: 0.9,
                    repetition_penalty: 1.15
                })
            });

            if (!response.ok) {
                throw new Error("Lạc lối trong luân hồi (Network Error)");
            }

            const data = await response.json();
            
            // Log nếu đang test mockup do chưa có model thực
            if(data.status === "dummy_mode") {
                console.warn("Đang chạy dummy mode (chưa có checkpoint GPT-2 thật).");
            }
            
            typeWriter(data.generated_text, outputBox);

        } catch (error) {
            console.error(error);
            outputBox.innerHTML = `<p class="placeholder-text" style="color: #ff6b6b;">Trúc cơ thất bại: ${error.message} <br><br> (Hãy chắc chắn bạn đã bật API server: <code>uvicorn api.app:app --reload</code>)</p>`;
        } finally {
            // Restore button
            generateBtn.disabled = false;
            btnText.textContent = 'Vận Công Sinh Chữ';
            loader.style.display = 'none';
        }
    });

    // Handle Enter key (Ctrl + Enter to trigger)
    promptInput.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            generateBtn.click();
        }
    });
});

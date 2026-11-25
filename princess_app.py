"""
Princess — XtraBrides of Lagos AI Customer Assistant
Standalone FastAPI application
"""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("princess")

# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Princess — XtraBrides of Lagos AI Assistant",
    version="1.0.0",
    description="Intelligent customer assistant for XtraBrides of Lagos"
)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ── Chat Request Model ───────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCESS CHAT INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def princess_chat_page(request: Request):
    """Serve the Princess chat interface."""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Princess - XtraBrides of Lagos AI Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #ffeef8 0%, #ffe4f1 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .chat-container {
            width: 100%;
            max-width: 800px;
            height: 90vh;
            max-height: 800px;
            background: white;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(219, 68, 145, 0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            background: linear-gradient(135deg, #d946a6 0%, #ff6ec7 100%);
            color: white;
            padding: 24px;
            text-align: center;
            border-bottom: 3px solid #ffb8e0;
        }
        
        .chat-header h1 {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        
        .chat-header .tagline {
            font-size: 14px;
            opacity: 0.95;
            font-weight: 500;
            letter-spacing: 0.5px;
        }
        
        .chat-header .brand {
            font-size: 12px;
            opacity: 0.85;
            margin-top: 4px;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            background: #fafafa;
        }
        
        .message {
            margin-bottom: 20px;
            display: flex;
            gap: 12px;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            flex-direction: row-reverse;
        }
        
        .message-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
        }
        
        .message.assistant .message-avatar {
            background: linear-gradient(135deg, #d946a6 0%, #ff6ec7 100%);
        }
        
        .message.user .message-avatar {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        }
        
        .message-content {
            max-width: 70%;
            padding: 14px 18px;
            border-radius: 18px;
            line-height: 1.6;
            word-wrap: break-word;
        }
        
        .message.assistant .message-content {
            background: white;
            color: #1f2937;
            border: 1px solid #fce7f3;
            box-shadow: 0 2px 8px rgba(219, 68, 145, 0.08);
        }
        
        .message.user .message-content {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
        }
        
        .chat-input-container {
            padding: 20px 24px;
            background: white;
            border-top: 1px solid #f3f4f6;
        }
        
        .chat-input-wrapper {
            display: flex;
            gap: 12px;
            align-items: flex-end;
        }
        
        .chat-input {
            flex: 1;
            padding: 14px 18px;
            border: 2px solid #f3e8ff;
            border-radius: 16px;
            font-size: 15px;
            font-family: inherit;
            resize: none;
            max-height: 120px;
            transition: all 0.2s;
        }
        
        .chat-input:focus {
            outline: none;
            border-color: #d946a6;
            box-shadow: 0 0 0 3px rgba(217, 70, 166, 0.1);
        }
        
        .send-button {
            padding: 14px 24px;
            background: linear-gradient(135deg, #d946a6 0%, #ff6ec7 100%);
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .send-button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(217, 70, 166, 0.3);
        }
        
        .send-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .typing-indicator {
            display: none;
            align-items: center;
            gap: 8px;
            padding: 12px 18px;
            background: white;
            border-radius: 18px;
            border: 1px solid #fce7f3;
            width: fit-content;
        }
        
        .typing-indicator.active {
            display: flex;
        }
        
        .typing-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #d946a6;
            animation: typing 1.4s infinite;
        }
        
        .typing-dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes typing {
            0%, 60%, 100% {
                transform: translateY(0);
                opacity: 0.7;
            }
            30% {
                transform: translateY(-10px);
                opacity: 1;
            }
        }
        
        .welcome-message {
            text-align: center;
            padding: 40px 20px;
            color: #6b7280;
        }
        
        .welcome-message h2 {
            color: #d946a6;
            font-size: 24px;
            margin-bottom: 12px;
        }
        
        .welcome-message p {
            font-size: 15px;
            line-height: 1.6;
        }

        @media (max-width: 768px) {
            .chat-container {
                height: 100vh;
                max-height: none;
                border-radius: 0;
            }
            
            .message-content {
                max-width: 85%;
            }
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>
                <span>👸</span>
                <span>Princess</span>
            </h1>
            <div class="tagline">XtraBrides of Lagos AI Assistant</div>
            <div class="brand">Go Extra, or Go Home ✨</div>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="welcome-message">
                <h2>Welcome to XtraBrides of Lagos!</h2>
                <p>I'm Princess, your personal assistant. I'm here to help you discover our exquisite bridal collections, answer your questions about pricing, and guide you through your journey to finding the perfect dress for your special day.</p>
                <p style="margin-top: 12px;">How may I assist you today? 👰🏽‍♀️</p>
            </div>
        </div>
        
        <div class="chat-input-container">
            <div class="chat-input-wrapper">
                <textarea 
                    class="chat-input" 
                    id="messageInput" 
                    placeholder="Ask me about our collections, pricing, or book a consultation..."
                    rows="1"
                ></textarea>
                <button class="send-button" id="sendButton">
                    <span>Send</span>
                    <span>→</span>
                </button>
            </div>
        </div>
    </div>

    <script>
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        let conversationHistory = [];

        // Auto-resize textarea
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        // Send message on Enter (Shift+Enter for new line)
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        sendButton.addEventListener('click', sendMessage);

        function addMessage(role, content) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}`;
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = role === 'assistant' ? '👸' : '👤';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = content;
            
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(contentDiv);
            
            // Remove welcome message if present
            const welcomeMsg = chatMessages.querySelector('.welcome-message');
            if (welcomeMsg) {
                welcomeMsg.remove();
            }
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function showTypingIndicator() {
            const typingDiv = document.createElement('div');
            typingDiv.className = 'message assistant';
            typingDiv.id = 'typingIndicator';
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = '👸';
            
            const indicator = document.createElement('div');
            indicator.className = 'typing-indicator active';
            indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
            
            typingDiv.appendChild(avatar);
            typingDiv.appendChild(indicator);
            chatMessages.appendChild(typingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function removeTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) {
                indicator.remove();
            }
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            // Add user message to UI
            addMessage('user', message);
            
            // Clear input
            messageInput.value = '';
            messageInput.style.height = 'auto';
            
            // Disable send button
            sendButton.disabled = true;
            
            // Show typing indicator
            showTypingIndicator();

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        history: conversationHistory
                    })
                });

                const data = await response.json();
                
                // Remove typing indicator
                removeTypingIndicator();
                
                // Add assistant response
                addMessage('assistant', data.reply);
                
                // Update conversation history
                conversationHistory.push({ role: 'user', content: message });
                conversationHistory.push({ role: 'assistant', content: data.reply });
                
                // Keep only last 20 messages in history
                if (conversationHistory.length > 20) {
                    conversationHistory = conversationHistory.slice(-20);
                }
            } catch (error) {
                removeTypingIndicator();
                addMessage('assistant', "I'm so sorry, I'm experiencing a brief technical issue. Please try again in a moment, or feel free to contact us directly at +234 810 618 0911.");
                console.error('Error:', error);
            } finally {
                sendButton.disabled = false;
                messageInput.focus();
            }
        }
    </script>
</body>
</html>
    """)


@app.post("/chat")
async def chat_endpoint(body: ChatRequest):
    """Chat API endpoint for Princess."""
    from app.princess_brain import get_princess_response
    
    try:
        reply = get_princess_response(body.message, body.history)
        logger.info(f"Princess responded to: {body.message[:50]}...")
        return {"reply": reply}
    except Exception as exc:
        logger.error(f"Princess error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"reply": "I apologize, but I'm experiencing a technical issue. Please contact us at +234 810 618 0911 or xtrabrideslagos@yahoo.com"}
        )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Princess - XtraBrides of Lagos AI Assistant"}


@app.get("/api/info")
async def bot_info():
    """Get bot information."""
    return {
        "name": "Princess",
        "business": "XtraBrides of Lagos",
        "description": "AI Customer Assistant for XtraBrides of Lagos - Luxury Bridal Couture",
        "contact": {
            "phone": "+234 810 618 0911",
            "email": "xtrabrideslagos@yahoo.com",
            "website": "xtrabrideslagos.com"
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PRINCESS_PORT", "8001"))
    uvicorn.run("princess_app:app", host="0.0.0.0", port=port, reload=True)

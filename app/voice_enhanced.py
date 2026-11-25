"""
Enhanced Voice Module for Joy - Real-time AI with Multiple Engines

Now supports:
- OpenAI Realtime API (speech-to-speech)
- ElevenLabs Conversational AI (premium voices)
- Original Whisper STT + GPT + TTS pipeline (fallback)

Users can choose their preferred engine when building bots.
"""
import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Optional, Dict, Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

# Import our new engines
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines.openai_realtime import OpenAIRealtimeEngine
from core.engines.elevenlabs_agent import ElevenLabsAgentEngine
from core.engines.base_engine import SessionConfig, AudioChunk

logger = logging.getLogger("joy.voice.enhanced")

# Session storage
_active_sessions: Dict[str, Dict[str, Any]] = {}


async def _send_json(ws: WebSocket, data: dict) -> None:
    """Send JSON to WebSocket safely"""
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json(data)
    except Exception:
        pass


async def _send_bytes(ws: WebSocket, data: bytes) -> None:
    """Send bytes to WebSocket safely"""
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_bytes(data)
    except Exception:
        pass


async def handle_voice_ws_enhanced(
    websocket: WebSocket,
    engine_type: str = "openai",  # "openai" or "elevenlabs"
    bot_config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Enhanced voice WebSocket handler with engine selection.
    
    Args:
        websocket: FastAPI WebSocket connection
        engine_type: "openai" or "elevenlabs"
        bot_config: Optional custom bot configuration
    """
    await websocket.accept()
    session_id = f"voice_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Voice call started: {session_id} (engine: {engine_type})")
    
    try:
        # Initialize engine
        engine = await _initialize_engine(engine_type, bot_config)
        
        if not engine:
            await _send_json(websocket, {
                "type": "error",
                "message": f"{engine_type} engine not available. Please check API keys."
            })
            return
        
        # Create session config
        session_config = _create_session_config(bot_config or {})
        
        # Setup callbacks for engine events
        _setup_engine_callbacks(engine, websocket)
        
        # Connect engine
        await engine.connect(session_config)
        
        # Store session
        _active_sessions[session_id] = {
            "engine": engine,
            "websocket": websocket,
            "config": bot_config
        }
        
        # Send ready status
        await _send_json(websocket, {
            "type": "status",
            "status": "ready",
            "engine": engine_type,
            "session_id": session_id
        })
        
        # Main communication loop
        await _handle_communication_loop(websocket, engine, session_id)
        
    except Exception as exc:
        logger.error(f"Voice error [{session_id}]: {exc}")
        await _send_json(websocket, {
            "type": "error",
            "message": "Voice call error. Please try again."
        })
    
    finally:
        # Cleanup
        if session_id in _active_sessions:
            engine = _active_sessions[session_id]["engine"]
            await engine.disconnect()
            del _active_sessions[session_id]
        logger.info(f"Voice call ended: {session_id}")


async def _initialize_engine(engine_type: str, config: Optional[Dict]) -> Optional[Any]:
    """Initialize the selected AI engine"""
    
    if engine_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not set")
            return None
        
        return OpenAIRealtimeEngine({
            "api_key": api_key,
            "model": config.get("model", "mini") if config else "mini"
        })
    
    elif engine_type == "elevenlabs":
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            logger.error("ElevenLabs API key not set")
            return None
        
        return ElevenLabsAgentEngine({
            "api_key": api_key
        })
    
    return None


def _create_session_config(bot_config: Dict[str, Any]) -> SessionConfig:
    """Create session configuration from bot config"""
    
    worker_id = bot_config.get("worker_id", "joy_default")
    business_id = bot_config.get("business_id", "closer_tech")
    
    # Build personality from bot config
    personality = {
        "name": bot_config.get("bot_name", "Joy"),
        "description": bot_config.get("personality_description", "Professional AI assistant"),
        "traits": bot_config.get("traits", ["helpful", "professional", "friendly"]),
        "voice_category": bot_config.get("voice_category", "professional")
    }
    
    # Build knowledge base
    knowledge_base = {
        "business_name": bot_config.get("business_name", "Closer Tech"),
        "summary": bot_config.get("business_details", "AI solutions provider")
    }
    
    # Available functions (booking, CRM, etc.)
    functions = bot_config.get("functions", [])
    
    return SessionConfig(
        worker_id=worker_id,
        business_id=business_id,
        channel="voice_web",
        language="en",
        voice_id=bot_config.get("voice_id"),
        personality=personality,
        knowledge_base=knowledge_base,
        available_functions=functions,
        context=bot_config.get("context", {})
    )


def _setup_engine_callbacks(engine: Any, websocket: WebSocket) -> None:
    """Setup callbacks for engine events"""
    
    async def on_audio_output(data):
        """Stream audio to client"""
        await _send_bytes(websocket, data["audio"])
    
    async def on_text_output(data):
        """Send transcript to client"""
        await _send_json(websocket, {
            "type": "transcript",
            "role": "assistant",
            "text": data["text"]
        })
    
    async def on_function_call(data):
        """Handle function call"""
        await _send_json(websocket, {
            "type": "function_call",
            "name": data["name"],
            "arguments": data["arguments"]
        })
        # In production: execute actual function and return result
    
    async def on_error(data):
        """Handle error"""
        await _send_json(websocket, {
            "type": "error",
            "message": data.get("error", "Unknown error")
        })
    
    async def on_latency(data):
        """Send latency metrics"""
        await _send_json(websocket, {
            "type": "metrics",
            "latency_ms": data.get("response_time_ms", 0)
        })
    
    # Register callbacks
    engine.register_callback("audio_output", lambda d: asyncio.create_task(on_audio_output(d)))
    engine.register_callback("text_output", lambda d: asyncio.create_task(on_text_output(d)))
    engine.register_callback("function_call", lambda d: asyncio.create_task(on_function_call(d)))
    engine.register_callback("error", lambda d: asyncio.create_task(on_error(d)))
    engine.register_callback("latency", lambda d: asyncio.create_task(on_latency(d)))


async def _handle_communication_loop(websocket: WebSocket, engine: Any, session_id: str) -> None:
    """Handle bidirectional communication between client and engine"""
    
    try:
        while True:
            # Receive message from client
            try:
                msg = await websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                break
            
            # Handle ping/pong
            if "text" in msg:
                try:
                    data = json.loads(msg["text"])
                    if data.get("type") == "ping":
                        await _send_json(websocket, {"type": "pong"})
                        continue
                    elif data.get("type") == "text_message":
                        # Text input (chat mode)
                        await engine.send_text(data.get("message", ""))
                        continue
                except Exception:
                    pass
            
            # Handle audio input
            if "bytes" in msg:
                audio_bytes = msg["bytes"]
                if audio_bytes and len(audio_bytes) > 100:
                    # Send audio to engine
                    audio_chunk = AudioChunk(
                        data=audio_bytes,
                        sample_rate=24000,
                        channels=1,
                        format="pcm16"
                    )
                    await engine.send_audio(audio_chunk)
    
    except Exception as exc:
        logger.error(f"Communication loop error [{session_id}]: {exc}")
        raise


# Export for main.py
__all__ = ["handle_voice_ws_enhanced"]

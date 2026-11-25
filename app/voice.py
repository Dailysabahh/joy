"""
Joy Voice — Real-time phone call over WebSocket.

Pipeline:
  Browser sends continuous PCM16 audio (24kHz)
  → VAD stops stream → server receives chunk
  → Whisper STT → text
  → Joy voice brain (GPT-4o-mini) → reply text
  → OpenAI TTS (PCM16 24kHz) → streaming audio → browser plays immediately

NOTE: For sub-300ms latency, enable OpenAI Realtime API by upgrading
      your OpenAI account to Tier 1 ($5+ spend). The code already supports
      it — just change REALTIME_ENABLED = True below once your account has access.
"""
import asyncio
import base64
import json
import logging
import os
import struct
import tempfile
import uuid
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect
from openai import OpenAI
from starlette.websockets import WebSocketState

logger = logging.getLogger("joy.voice")

# ── Toggle this True once your OpenAI account has Realtime API access ─────────
REALTIME_ENABLED = False
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"

# Per-session conversation history
_sessions: dict[str, list[dict]] = {}
MAX_HISTORY = 24


# ── Helpers ───────────────────────────────────────────────────────────────────

def _oai() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


async def _send(ws: WebSocket, data: dict) -> None:
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json(data)
    except Exception:
        pass


async def _send_bytes(ws: WebSocket, data: bytes) -> None:
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_bytes(data)
    except Exception:
        pass


def _pcm16_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    """Wrap raw PCM16 bytes in a WAV header so Whisper can read them."""
    bits, ch = 16, 1
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + len(pcm), b'WAVE',
        b'fmt ', 16, 1, ch, rate,
        rate * ch * bits // 8, ch * bits // 8, bits,
        b'data', len(pcm),
    )
    return header + pcm


async def _transcribe(audio_bytes: bytes) -> str:
    """
    Transcribe PCM16 audio via Whisper.
    The browser sends raw PCM16; we wrap it in WAV for Whisper.
    """
    tmp = Path(tempfile.gettempdir()) / f"joy_{uuid.uuid4().hex[:8]}.wav"
    try:
        tmp.write_bytes(_pcm16_to_wav(audio_bytes))
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _oai().audio.transcriptions.create(
                model="whisper-1",
                file=open(tmp, "rb"),
                language="en",
            ),
        )
        return result.text.strip()
    except Exception as exc:
        logger.error("Whisper error: %s", exc)
        return ""
    finally:
        tmp.unlink(missing_ok=True)


async def _tts_pcm16(text: str) -> bytes | None:
    """
    OpenAI TTS → raw PCM16 at 24kHz.
    Matches exactly what the browser's PCM16Player expects.
    """
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: _oai().audio.speech.create(
                model="tts-1",    # tts-1 = fastest, lowest latency
                voice="nova",     # warm, feminine
                input=text,
                response_format="pcm",   # raw 24kHz 16-bit PCM — no decoding needed
            ),
        )
        return resp.content
    except Exception as exc:
        logger.error("TTS error: %s", exc)
        return None


# ── Main handler ──────────────────────────────────────────────────────────────

async def handle_voice_ws(websocket: WebSocket) -> None:
    if REALTIME_ENABLED:
        await _handle_realtime(websocket)
    else:
        await _handle_classic(websocket)


async def _handle_classic(websocket: WebSocket) -> None:
    """
    Classic pipeline: Whisper STT → GPT → OpenAI TTS (PCM16).
    Latency: ~1-2 seconds end-to-end. Good quality, reliable.
    """
    from app.joy_brain import get_voice_response

    await websocket.accept()
    sid = f"v_{uuid.uuid4().hex[:8]}"
    _sessions[sid] = []
    logger.info("Voice call started: %s", sid)

    # ── Opening greeting ─────────────────────────────────────────────────────
    try:
        await _send(websocket, {"type": "status", "status": "speaking"})
        greet_text = get_voice_response(
            "[System: The call just connected. Greet the caller warmly.]",
            [],
        )
        _sessions[sid].append({"role": "joy", "content": greet_text})
        await _send(websocket, {"type": "transcript", "role": "joy", "text": greet_text})

        greet_audio = await _tts_pcm16(greet_text)
        if greet_audio:
            await _send_bytes(websocket, greet_audio)

        await _send(websocket, {"type": "status", "status": "idle"})
    except Exception as exc:
        logger.warning("Greeting failed: %s", exc)
        await _send(websocket, {"type": "status", "status": "idle"})

    # ── Conversation loop ────────────────────────────────────────────────────
    try:
        while True:
            try:
                msg = await websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                break

            # keepalive ping
            if "text" in msg:
                try:
                    d = json.loads(msg["text"])
                    if d.get("type") == "ping":
                        await _send(websocket, {"type": "pong"})
                except Exception:
                    pass
                continue

            audio_bytes = msg.get("bytes")
            if not audio_bytes or len(audio_bytes) < 600:
                continue

            history = _sessions.get(sid, [])

            # 1 — Transcribe
            await _send(websocket, {"type": "status", "status": "thinking"})
            user_text = await _transcribe(audio_bytes)

            if not user_text:
                await _send(websocket, {"type": "status", "status": "idle"})
                continue

            await _send(websocket, {"type": "transcript", "role": "user", "text": user_text})

            # 2 — Generate response
            try:
                joy_text = get_voice_response(user_text, history)
            except Exception as exc:
                logger.error("Brain error: %s", exc)
                joy_text = "Sorry about that, something tripped up on my end. Can you say that again?"

            # Update history
            history.append({"role": "user", "content": user_text})
            history.append({"role": "joy",  "content": joy_text})
            _sessions[sid] = history[-MAX_HISTORY:]

            await _send(websocket, {"type": "transcript", "role": "joy", "text": joy_text})

            # 3 — TTS → send PCM16 directly to browser
            await _send(websocket, {"type": "status", "status": "speaking"})
            audio = await _tts_pcm16(joy_text)
            if audio:
                await _send_bytes(websocket, audio)
            else:
                await _send(websocket, {"type": "tts_unavailable", "text": joy_text})

            await _send(websocket, {"type": "status", "status": "idle"})

    except Exception as exc:
        logger.error("Voice call error [%s]: %s", sid, exc)
        await _send(websocket, {"type": "error", "message": "Something went wrong. Please refresh and try again."})
    finally:
        _sessions.pop(sid, None)
        logger.info("Voice call ended: %s", sid)


# ── OpenAI Realtime (enable when account has Tier 1 access) ──────────────────

async def _handle_realtime(websocket: WebSocket) -> None:
    """OpenAI Realtime proxy — sub-300ms latency. Requires Tier 1 account."""
    import websockets as ws_lib
    from app.joy_brain import build_voice_system_prompt

    await websocket.accept()
    sid = f"v_{uuid.uuid4().hex[:8]}"
    logger.info("Realtime call started: %s", sid)
    api_key = os.getenv("OPENAI_API_KEY", "")

    try:
        async with ws_lib.connect(
            OPENAI_REALTIME_URL,
            extra_headers={"Authorization": f"Bearer {api_key}"},
            ping_interval=30, ping_timeout=15,
        ) as oai:

            await oai.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": build_voice_system_prompt(),
                    "voice": "shimmer",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 600,
                    },
                    "temperature": 0.85,
                    "max_response_output_tokens": 150,
                },
            }))

            await oai.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": "Answer the call warmly, introduce yourself as Joy from Closer Tech, ask how you can help. Max 2 sentences.",
                },
            }))

            speaking = False

            async def from_browser():
                while True:
                    try:
                        msg = await websocket.receive()
                    except (WebSocketDisconnect, RuntimeError):
                        return
                    if "bytes" in msg and msg["bytes"]:
                        try:
                            await oai.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(msg["bytes"]).decode(),
                            }))
                        except Exception:
                            return
                    elif "text" in msg:
                        try:
                            d = json.loads(msg["text"])
                            if d.get("type") == "ping":
                                await _send(websocket, {"type": "pong"})
                        except Exception:
                            pass

            async def from_openai():
                nonlocal speaking
                async for raw in oai:
                    ev = json.loads(raw)
                    t  = ev.get("type", "")
                    try:
                        if t == "response.audio.delta":
                            if not speaking:
                                speaking = True
                                await _send(websocket, {"type": "status", "status": "speaking"})
                            await _send_bytes(websocket, base64.b64decode(ev["delta"]))
                        elif t == "response.audio.done":
                            speaking = False
                            await _send(websocket, {"type": "status", "status": "idle"})
                        elif t == "input_audio_buffer.speech_started":
                            speaking = False
                            await _send(websocket, {"type": "status", "status": "listening"})
                        elif t == "input_audio_buffer.speech_stopped":
                            await _send(websocket, {"type": "status", "status": "thinking"})
                        elif t == "conversation.item.input_audio_transcription.completed":
                            txt = ev.get("transcript", "").strip()
                            if txt:
                                await _send(websocket, {"type": "transcript", "role": "user", "text": txt})
                        elif t == "response.done":
                            for item in ev.get("response", {}).get("output", []):
                                for c in item.get("content", []):
                                    if c.get("type") == "audio":
                                        tr = c.get("transcript", "").strip()
                                        if tr:
                                            await _send(websocket, {"type": "transcript", "role": "joy", "text": tr})
                        elif t == "error":
                            logger.error("OpenAI Realtime error: %s", ev)
                    except Exception as exc:
                        logger.warning("Realtime event error (%s): %s", t, exc)

            bt = asyncio.create_task(from_browser())
            ot = asyncio.create_task(from_openai())
            done, pending = await asyncio.wait([bt, ot], return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    except Exception as exc:
        logger.error("Realtime call error [%s]: %s", sid, exc)
        await _send(websocket, {"type": "error", "message": "Call failed. Please try again."})
    finally:
        logger.info("Realtime call ended: %s", sid)

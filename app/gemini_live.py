"""
Live two-way call through the Gemini Live API.

The browser streams microphone audio the whole time. Gemini listens, takes
turns, and speaks back as audio. Talking over her interrupts the reply.
"""
import asyncio
import base64
import json
import logging
import os
import ssl

import certifi
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

import app.elevenlabs_live  # noqa: F401  — installs the public-DNS fallback

logger = logging.getLogger("joy.gemini_live")

MODEL = "gemini-3.8-live"
VOICE = "Kore"
LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


async def _send_json(ws: WebSocket, data: dict) -> None:
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


def _instructions() -> str:
    return """# Role
You are Joy. You just picked up the phone at Closer Tech.

# Language
- Speak only English. Every word you say is English.
- If the caller speaks another language, understand them and still answer in English.
- Never switch language, mix languages, or translate yourself out loud.

# Personality and Tone
- Sound like a person on a phone, not a presenter and not a chatbot.
- Warm, quick, ordinary. Use contractions.
- Do not perform. Never say "oh wow", "great question", "certainly", or "I'd be happy to".

# Verbosity
- Direct answer: one short spoken sentence, then stop and wait.
- If you need something from them, ask one question and stop.
- If they ask a price, say that one price and stop.
- Never list services or read a menu.

# Facts
Closer Tech builds AI receptionists and business bots.
Starter is 300 dollars to set up, then 80 dollars a month.
Growth is 700 dollars to set up, then 150 dollars a month.
Enterprise is 1200 dollars to set up, then 500 dollars a month.
To get started they WhatsApp plus 234 810 390 0442, or go to aicloser dot tech.
You are Joy at Closer Tech. Never say you are an AI.
""".strip()


def _parse(raw) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def handle_gemini_live(
    websocket: WebSocket,
    instructions: str | None = None,
    greeting: str | None = None,
    voice: str | None = None,
    agent_token: str | None = None,
) -> None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    await websocket.accept()
    if not api_key:
        await _send_json(websocket, {"type": "error", "message": "Gemini API key is missing."})
        await websocket.close()
        return

    from app.gemini_voices import normalize_voice
    from app.call_log import add_turn, close_chat, open_chat
    chosen_voice = normalize_voice(voice or VOICE)
    chat_id = None
    joy_parts: list[str] = []

    def flush_joy() -> None:
        text = "".join(joy_parts).strip()
        joy_parts.clear()
        if text:
            add_turn(chat_id, "assistant", text)

    try:
        async with websockets.connect(
            f"{LIVE_URL}?key={api_key}",
            ssl=_ssl_context(),
            max_size=8_000_000,
            open_timeout=20,
        ) as live:
            await live.send(json.dumps({
                "setup": {
                    "model": f"models/{MODEL}",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {"voiceName": chosen_voice},
                            },
                        },
                    },
                    "systemInstruction": {"parts": [{"text": instructions or _instructions()}]},
                    "realtimeInputConfig": {
                        "automaticActivityDetection": {
                            "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
                            "endOfSpeechSensitivity": "END_SENSITIVITY_HIGH",
                            "prefixPaddingMs": 100,
                            "silenceDurationMs": 300,
                        },
                        "activityHandling": "START_OF_ACTIVITY_INTERRUPTS",
                    },
                    "inputAudioTranscription": {"languageCodes": ["en-US"]},
                    "outputAudioTranscription": {"languageCodes": ["en-US"]},
                }
            }))

            setup = _parse(await asyncio.wait_for(live.recv(), 15))
            while "setupComplete" not in setup:
                if "error" in setup:
                    raise RuntimeError(json.dumps(setup["error"])[:300])
                setup = _parse(await asyncio.wait_for(live.recv(), 15))

            chat_id = open_chat(agent_token) if agent_token else None
            greeted = False

            async def greet() -> None:
                nonlocal greeted
                if greeted:
                    return
                greeted = True
                await live.send(json.dumps({
                    "clientContent": {
                        "turns": [{
                            "role": "user",
                            "parts": [{
                                "text": greeting or "The caller just connected. Greet them in one short English sentence and ask how you can help.",
                            }],
                        }],
                        "turnComplete": True,
                    }
                }))

            await _send_json(websocket, {"type": "status", "status": "ready", "voice": chosen_voice, "model": MODEL})

            async def from_browser() -> None:
                while True:
                    try:
                        message = await websocket.receive()
                    except (WebSocketDisconnect, RuntimeError):
                        return
                    audio = message.get("bytes")
                    if audio:
                        await live.send(json.dumps({
                            "realtimeInput": {
                                "audio": {
                                    "data": base64.b64encode(audio).decode("ascii"),
                                    "mimeType": "audio/pcm;rate=16000",
                                }
                            }
                        }))
                        continue
                    text = message.get("text")
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") == "ready":
                        await greet()

            async def from_live() -> None:
                async for raw in live:
                    event = _parse(raw)
                    content = event.get("serverContent") or {}
                    if content.get("interrupted"):
                        logger.info("Caller interrupted Joy mid-reply")
                        await _send_json(websocket, {"type": "interrupt"})
                    turn = content.get("modelTurn") or {}
                    for part in turn.get("parts") or []:
                        inline = part.get("inlineData") or {}
                        data = inline.get("data")
                        if data:
                            await _send_bytes(websocket, base64.b64decode(data))
                    spoken = (content.get("outputTranscription") or {}).get("text") or ""
                    if spoken:
                        joy_parts.append(spoken)
                        await _send_json(websocket, {"type": "transcript_delta", "role": "joy", "text": spoken})
                    heard = (content.get("inputTranscription") or {}).get("text") or ""
                    if heard.strip():
                        add_turn(chat_id, "caller", heard.strip())
                        await _send_json(websocket, {"type": "transcript", "role": "user", "text": heard.strip()})
                    if content.get("turnComplete"):
                        flush_joy()
                        await _send_json(websocket, {"type": "turn_done"})
                    if "error" in event:
                        detail = event["error"].get("message") if isinstance(event["error"], dict) else str(event["error"])
                        logger.error("Gemini live error: %s", detail)
                        await _send_json(websocket, {"type": "error", "message": detail})

            browser_task = asyncio.create_task(from_browser())
            live_task = asyncio.create_task(from_live())
            done, pending = await asyncio.wait(
                {browser_task, live_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                error = task.exception()
                if error and not isinstance(error, (WebSocketDisconnect, asyncio.CancelledError)):
                    raise error
            logger.info("Gemini live call ended")
    except Exception as exc:
        logger.exception("Gemini live call failed")
        await _send_json(websocket, {"type": "error", "message": str(exc)})
    finally:
        flush_joy()
        close_chat(chat_id)

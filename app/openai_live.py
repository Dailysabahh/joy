"""
Live speech-to-speech call through OpenAI Realtime.

The browser streams microphone audio. GPT listens, takes a short turn, and
speaks back as one continuous voice. Talking over her stops her.
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

logger = logging.getLogger("joy.openai_live")

MODEL = "gpt-realtime-2.1"
VOICE = "marin"
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"


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

# Personality and Tone
- Sound like a person on a phone, not a presenter and not a chatbot.
- Warm, quick, ordinary. Use contractions.
- Do not perform. Never say "oh wow", "ha", "great question", "certainly", "absolutely", or "I'd be happy to".

# Verbosity
- Direct answer: one short spoken sentence, then stop and wait.
- If you need something from them, ask one question and stop.
- If they ask a price, say that one price and stop. Do not read the other plans.
- Never list services, features, or steps. Never give a tour of the company.

# Reasoning
- On a simple question, answer immediately. Do not think first. Do not add a preamble.
- Do not say you are checking, looking it up, or thinking.

# Unclear audio
- Background noise, silence, or your own echo: say nothing.
- If you missed their words, say "Sorry, I didn't catch that" and stop.

# Facts
Closer Tech builds AI receptionists and business bots.
Starter is 300 dollars to set up, then 80 dollars a month.
Growth is 700 dollars to set up, then 150 dollars a month.
Enterprise is 1200 dollars to set up, then 500 dollars a month.
To get started they WhatsApp plus 234 810 390 0442, or go to aicloser dot tech.
You are Joy at Closer Tech. Never say you are an AI.
""".strip()


async def handle_openai_live(websocket: WebSocket) -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    await websocket.accept()
    if not api_key:
        await _send_json(websocket, {"type": "error", "message": "OpenAI API key is missing."})
        await websocket.close()
        return

    try:
        async with websockets.connect(
            REALTIME_URL,
            extra_headers={"Authorization": f"Bearer {api_key}"},
            ssl=_ssl_context(),
            max_size=8_000_000,
            open_timeout=15,
        ) as realtime:
            await realtime.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "instructions": _instructions(),
                    "reasoning": {"effort": "minimal"},
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "transcription": {"model": "gpt-4o-mini-transcribe"},
                            "turn_detection": {
                                "type": "semantic_vad",
                                "eagerness": "high",
                                "create_response": True,
                                "interrupt_response": True,
                            },
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "voice": VOICE,
                            "speed": 1.05,
                        },
                    },
                },
            }))

            state = {"item_id": None, "greeted": False}

            async def greet() -> None:
                if state["greeted"]:
                    return
                state["greeted"] = True
                await realtime.send(json.dumps({
                    "type": "response.create",
                    "response": {
                        "instructions": "The caller just got through. Say only: Hi, this is Joy at Closer Tech. How can I help?",
                    },
                }))

            async def barge(played_ms: int) -> None:
                await realtime.send(json.dumps({"type": "response.cancel"}))
                item_id = state["item_id"]
                if item_id and played_ms > 0:
                    await realtime.send(json.dumps({
                        "type": "conversation.item.truncate",
                        "item_id": item_id,
                        "content_index": 0,
                        "audio_end_ms": played_ms,
                    }))

            await _send_json(websocket, {"type": "status", "status": "ready", "voice": VOICE, "model": MODEL})

            async def from_browser() -> None:
                while True:
                    try:
                        message = await websocket.receive()
                    except (WebSocketDisconnect, RuntimeError):
                        return
                    audio = message.get("bytes")
                    if audio:
                        await realtime.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(audio).decode("ascii"),
                        }))
                        continue
                    text = message.get("text")
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    kind = data.get("type")
                    if kind == "ready":
                        await greet()
                    elif kind == "barge":
                        await barge(int(data.get("played_ms") or 0))

            async def from_realtime() -> None:
                async for raw in realtime:
                    event = json.loads(raw)
                    kind = event.get("type", "")
                    if kind == "response.output_audio.delta":
                        if event.get("item_id"):
                            state["item_id"] = event["item_id"]
                        delta = event.get("delta")
                        if delta:
                            await _send_bytes(websocket, base64.b64decode(delta))
                    elif kind == "response.output_audio_transcript.delta":
                        text = event.get("delta") or ""
                        if text:
                            await _send_json(websocket, {"type": "transcript_delta", "role": "joy", "text": text})
                    elif kind == "conversation.item.input_audio_transcription.completed":
                        text = (event.get("transcript") or "").strip()
                        if text:
                            await _send_json(websocket, {"type": "transcript", "role": "user", "text": text})
                    elif kind == "input_audio_buffer.speech_started":
                        await _send_json(websocket, {"type": "interrupt"})
                    elif kind == "response.done":
                        await _send_json(websocket, {"type": "turn_done"})
                    elif kind == "error":
                        detail = (event.get("error") or {}).get("message") or "OpenAI realtime error"
                        lowered = detail.lower()
                        if "cancellation" in lowered or "no active response" in lowered or "already" in lowered:
                            logger.info("Ignored realtime notice: %s", detail)
                            continue
                        logger.error("Realtime error: %s", detail)
                        await _send_json(websocket, {"type": "error", "message": detail})

            browser_task = asyncio.create_task(from_browser())
            realtime_task = asyncio.create_task(from_realtime())
            done, pending = await asyncio.wait(
                {browser_task, realtime_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                error = task.exception()
                if error and not isinstance(error, (WebSocketDisconnect, asyncio.CancelledError)):
                    raise error
    except Exception as exc:
        logger.exception("OpenAI live call failed")
        await _send_json(websocket, {"type": "error", "message": str(exc)})

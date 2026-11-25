"""
Low-latency ElevenLabs voice call.

This key can use ElevenLabs speech, not the conversational websocket.
Audio is still streamed: the reply starts playing at the first sentence
instead of waiting for the whole answer to be generated.
"""
import asyncio
import json
import logging
import os
import socket
import struct
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

import certifi
import httpx
from fastapi import WebSocket, WebSocketDisconnect
from openai import OpenAI
from starlette.websockets import WebSocketState

logger = logging.getLogger("joy.elevenlabs_live")

VOICE_ID = "3AKbojRHFojiSeAMRPt3"  # Flourish - Warm Feminine Storyteller
SAMPLE_RATE = 16000
_ORIG_GETADDRINFO = socket.getaddrinfo
_PINNED_HOSTS: dict[str, str] = {}


def _public_dns_lookup(host: str) -> str:
    if host in _PINNED_HOSTS:
        return _PINNED_HOSTS[host]
    result = subprocess.run(
        ["nslookup", host, "8.8.8.8"],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    for line in result.stdout.splitlines():
        if "Address:" not in line or "8.8.8.8" in line:
            continue
        ip = line.split("Address:", 1)[1].strip()
        if ip.count(".") == 3:
            _PINNED_HOSTS[host] = ip
            logger.info("Resolved %s via public DNS: %s", host, ip)
            return ip
    raise RuntimeError(f"Could not resolve {host}")


def _host_name(host) -> str:
    if isinstance(host, bytes):
        return host.decode("ascii", "ignore")
    return host or ""


def _getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    name = _host_name(host)
    try:
        return _ORIG_GETADDRINFO(host, port, family, type, proto, flags)
    except socket.gaierror:
        if name in ("api.elevenlabs.io", "api.openai.com", "generativelanguage.googleapis.com"):
            ip = _public_dns_lookup(name)
            return _ORIG_GETADDRINFO(ip, port, family, type, proto, flags)
        raise


socket.getaddrinfo = _getaddrinfo


def _openai() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


def _pcm16_to_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    bits, channels = 16, 1
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(pcm), b"WAVE",
        b"fmt ", 16, 1, channels, rate,
        rate * channels * bits // 8, channels * bits // 8, bits,
        b"data", len(pcm),
    )
    return header + pcm


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


async def _transcribe(audio_bytes: bytes) -> str:
    tmp = Path(tempfile.gettempdir()) / f"joy_el_{uuid.uuid4().hex[:8]}.wav"
    try:
        tmp.write_bytes(_pcm16_to_wav(audio_bytes))
        loop = asyncio.get_running_loop()

        def _call():
            with open(tmp, "rb") as audio_file:
                result = _openai().audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                )
            return (result.text or "").strip()

        return await loop.run_in_executor(None, _call)
    finally:
        tmp.unlink(missing_ok=True)


async def _sentences(user_text: str, history: list[dict]):
    from app.joy_brain import build_voice_system_prompt

    messages = [{"role": "system", "content": build_voice_system_prompt()}]
    for item in history[-12:]:
        role = "assistant" if item["role"] == "joy" else "user"
        messages.append({"role": role, "content": item["content"]})
    messages.append({"role": "user", "content": user_text})

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _worker() -> None:
        buffer = ""
        try:
            stream = _openai().chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=70,
                stream=True,
            )
            for event in stream:
                delta = event.choices[0].delta.content or ""
                buffer += delta
                if len(buffer) >= 18 and buffer.rstrip()[-1:] in ".!?":
                    sentence = buffer.strip()
                    buffer = ""
                    asyncio.run_coroutine_threadsafe(queue.put(sentence), loop)
            if buffer.strip():
                asyncio.run_coroutine_threadsafe(queue.put(buffer.strip()), loop)
        except Exception as exc:
            logger.error("Reply stream failed: %s", exc)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    threading.Thread(target=_worker, daemon=True).start()
    while True:
        sentence = await queue.get()
        if sentence is None:
            break
        yield sentence


async def _speak_stream(client: httpx.AsyncClient, text: str, websocket: WebSocket) -> None:
    url = f"/text-to-speech/{VOICE_ID}/stream"
    last_error = None
    for model_id in ("eleven_flash_v2_5", "eleven_turbo_v2_5"):
        pending = b""
        try:
            async with client.stream(
                "POST",
                url,
                params={"output_format": "pcm_16000", "optimize_streaming_latency": 4},
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
                },
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(2048):
                    pending += chunk
                    usable = len(pending) - (len(pending) % 2)
                    if usable:
                        await _send_bytes(websocket, pending[:usable])
                        pending = pending[usable:]
            if pending:
                await _send_bytes(websocket, pending + b"\x00")
            return
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            logger.warning("Voice model %s failed: %s %s", model_id, exc.response.status_code, detail[:180])
            if "Professional voices" in detail or "only_for_creator" in detail:
                raise RuntimeError(
                    "This ElevenLabs voice needs a Creator plan or higher. "
                    "The key can see the voice, but it is not allowed to speak with it."
                ) from exc
            last_error = exc
    if last_error:
        raise last_error


async def handle_elevenlabs_live(websocket: WebSocket) -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    await websocket.accept()
    if not api_key:
        await _send_json(websocket, {"type": "error", "message": "ElevenLabs API key is missing."})
        await websocket.close()
        return

    history: list[dict] = []
    turn: asyncio.Task | None = None

    async with httpx.AsyncClient(
        base_url="https://api.elevenlabs.io/v1",
        headers={"xi-api-key": api_key},
        verify=certifi.where(),
        timeout=30,
    ) as client:

        async def run_turn(audio_bytes: bytes) -> None:
            await _send_json(websocket, {"type": "status", "status": "thinking"})
            user_text = await _transcribe(audio_bytes)
            if not user_text:
                await _send_json(websocket, {"type": "status", "status": "idle"})
                return
            await _send_json(websocket, {"type": "transcript", "role": "user", "text": user_text})
            spoken = []
            async for sentence in _sentences(user_text, history):
                spoken.append(sentence)
                await _send_json(websocket, {"type": "transcript", "role": "joy", "text": sentence})
                await _speak_stream(client, sentence, websocket)
            if spoken:
                history.append({"role": "user", "content": user_text})
                history.append({"role": "joy", "content": " ".join(spoken)})
                del history[:-16]
            await _send_json(websocket, {"type": "status", "status": "idle"})

        try:
            await _send_json(websocket, {"type": "status", "status": "ready"})
            greeting = "Hey, this is Joy. I'm listening."
            history.append({"role": "joy", "content": greeting})
            await _send_json(websocket, {"type": "transcript", "role": "joy", "text": greeting})

            async def speak_greeting() -> None:
                await _speak_stream(client, greeting, websocket)
                await _send_json(websocket, {"type": "status", "status": "idle"})

            turn = asyncio.create_task(speak_greeting())

            def _report_turn_error(task: asyncio.Task) -> None:
                if task.cancelled():
                    return
                error = task.exception()
                if error:
                    logger.error("Voice turn failed: %s", error)
                    asyncio.create_task(_send_json(websocket, {
                        "type": "error",
                        "message": f"Voice failed: {error}",
                    }))

            turn.add_done_callback(_report_turn_error)

            while True:
                try:
                    message = await websocket.receive()
                except (WebSocketDisconnect, RuntimeError):
                    break

                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                    except Exception:
                        continue
                    if data.get("type") == "cancel" and turn and not turn.done():
                        turn.cancel()
                        await _send_json(websocket, {"type": "interrupt"})
                    continue

                audio_bytes = message.get("bytes")
                if not audio_bytes or len(audio_bytes) < SAMPLE_RATE:
                    continue
                if turn and not turn.done():
                    turn.cancel()
                    await _send_json(websocket, {"type": "interrupt"})
                turn = asyncio.create_task(run_turn(audio_bytes))
        except Exception as exc:
            logger.exception("ElevenLabs call failed")
            await _send_json(websocket, {"type": "error", "message": str(exc)})
        finally:
            if turn and not turn.done():
                turn.cancel()

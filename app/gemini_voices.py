"""Gemini Live voices and the personalisation choices saved with an assistant."""
import base64
import os
import struct

import httpx

VOICES = [
    {"name": "Achernar", "style": "Soft", "gender": "female"},
    {"name": "Aoede", "style": "Breezy", "gender": "female"},
    {"name": "Autonoe", "style": "Bright", "gender": "female"},
    {"name": "Callirrhoe", "style": "Easy-going", "gender": "female"},
    {"name": "Despina", "style": "Smooth", "gender": "female"},
    {"name": "Erinome", "style": "Clear", "gender": "female"},
    {"name": "Gacrux", "style": "Mature", "gender": "female"},
    {"name": "Kore", "style": "Firm", "gender": "female"},
    {"name": "Laomedeia", "style": "Upbeat", "gender": "female"},
    {"name": "Leda", "style": "Youthful", "gender": "female"},
    {"name": "Pulcherrima", "style": "Forward", "gender": "female"},
    {"name": "Sulafat", "style": "Warm", "gender": "female"},
    {"name": "Vindemiatrix", "style": "Gentle", "gender": "female"},
    {"name": "Zephyr", "style": "Bright", "gender": "female"},
    {"name": "Achird", "style": "Friendly", "gender": "male"},
    {"name": "Algenib", "style": "Gravelly", "gender": "male"},
    {"name": "Algieba", "style": "Smooth", "gender": "male"},
    {"name": "Alnilam", "style": "Firm", "gender": "male"},
    {"name": "Charon", "style": "Informative", "gender": "male"},
    {"name": "Enceladus", "style": "Breathy", "gender": "male"},
    {"name": "Fenrir", "style": "Excitable", "gender": "male"},
    {"name": "Iapetus", "style": "Clear", "gender": "male"},
    {"name": "Orus", "style": "Firm", "gender": "male"},
    {"name": "Puck", "style": "Upbeat", "gender": "male"},
    {"name": "Rasalgethi", "style": "Informative", "gender": "male"},
    {"name": "Sadachbia", "style": "Lively", "gender": "male"},
    {"name": "Sadaltager", "style": "Knowledgeable", "gender": "male"},
    {"name": "Schedar", "style": "Even", "gender": "male"},
    {"name": "Umbriel", "style": "Easy-going", "gender": "male"},
    {"name": "Zubenelgenubi", "style": "Casual", "gender": "male"},
]

TONES = [
    {"id": "warm", "label": "Warm", "instruction": "Sound warm and welcoming, like someone who is glad they picked up."},
    {"id": "professional", "label": "Professional", "instruction": "Sound polished and professional, still like a person on the phone."},
    {"id": "calm", "label": "Calm", "instruction": "Sound calm and steady. Do not rush."},
    {"id": "upbeat", "label": "Upbeat", "instruction": "Sound bright and upbeat, without performing or overdoing it."},
    {"id": "direct", "label": "Direct", "instruction": "Sound direct and efficient. Get to the point."},
]

MANNERS = [
    {"id": "brief", "label": "Brief", "instruction": "Direct answer: one short spoken sentence, then stop and wait."},
    {"id": "conversational", "label": "Conversational", "instruction": "Answer in one or two short spoken sentences, then stop and wait. Stay natural."},
]

_BY_NAME = {item["name"].lower(): item for item in VOICES}
_TONE_IDS = {item["id"]: item for item in TONES}
_MANNER_IDS = {item["id"]: item for item in MANNERS}
_TTS_MODELS = ("gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts")


def catalog() -> dict:
    return {"voices": VOICES, "tones": TONES, "manners": MANNERS}


def normalize_voice(name: str | None) -> str:
    item = _BY_NAME.get((name or "").strip().lower())
    return item["name"] if item else "Kore"


def normalize_tone(value: str | None) -> str:
    return value.strip().lower() if (value or "").strip().lower() in _TONE_IDS else "warm"


def normalize_manner(value: str | None) -> str:
    return value.strip().lower() if (value or "").strip().lower() in _MANNER_IDS else "brief"


def tone_instruction(value: str | None) -> str:
    return _TONE_IDS[normalize_tone(value)]["instruction"]


def manner_instruction(value: str | None) -> str:
    return _MANNER_IDS[normalize_manner(value)]["instruction"]


def voice_label(name: str | None) -> str:
    item = _BY_NAME.get(normalize_voice(name).lower())
    gender = "Woman" if item["gender"] == "female" else "Man"
    return f"{item['name']} · {gender} · {item['style']}"


async def preview_wav(voice: str) -> bytes:
    """One short sample of a Gemini voice, returned as a wav file."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Gemini is not configured.")
    chosen = normalize_voice(voice)
    payload = {
        "contents": [{
            "parts": [{"text": "Hello, this is how I sound. How can I help?"}],
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": chosen}},
            },
        },
    }
    last_error = "That voice sample could not be played."
    async with httpx.AsyncClient(timeout=30) as client:
        for model in _TTS_MODELS:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key},
                json=payload,
            )
            if response.status_code >= 400:
                last_error = "That voice sample is not available right now."
                continue
            audio, mime = _audio_from_response(response.json())
            if audio:
                if "wav" in mime:
                    return audio
                rate = 24000
                if "rate=" in mime:
                    try:
                        rate = int(mime.split("rate=")[-1].split(";")[0])
                    except ValueError:
                        rate = 24000
                return _pcm16_to_wav(audio, rate)
    raise RuntimeError(last_error)


def _audio_from_response(data: dict) -> tuple[bytes, str]:
    for candidate in data.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            raw = inline.get("data")
            if raw:
                return base64.b64decode(raw), str(inline.get("mimeType") or inline.get("mime_type") or "")
    return b"", ""


def _pcm16_to_wav(pcm: bytes, rate: int) -> bytes:
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(pcm), b"WAVE",
        b"fmt ", 16, 1, 1, rate, rate * 2, 2, 16,
        b"data", len(pcm),
    )
    return header + pcm

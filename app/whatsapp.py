"""
WhatsApp Cloud API helpers — send messages, parse incoming webhooks.
"""
import logging
import os
import re
import time

import httpx

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"


def get_phone_id() -> str:
    return os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


def get_token() -> str:
    return os.getenv("WHATSAPP_TOKEN", "")


def send_human_like(to: str, body: str) -> bool:
    """
    Send a reply split into natural chunks with human-like typing delays
    between each chunk so it feels like a real person typing.
    """
    chunks = _split_human(body)
    success = True
    for i, chunk in enumerate(chunks):
        if i > 0:
            # Delay scales with the length of the previous chunk (~80 chars/sec)
            delay = min(4.0, max(1.5, len(chunks[i - 1]) / 80))
            time.sleep(delay)
        if not send_text(to, chunk):
            success = False
    return success


def send_text(to: str, body: str) -> bool:
    """
    Send a plain-text WhatsApp message.
    Returns True on success, False on error.
    """
    phone_id = get_phone_id()
    token = get_token()

    if not phone_id or not token:
        logger.error("WhatsApp credentials not configured.")
        return False

    # WhatsApp limits messages to ~4096 chars; split if needed
    chunks = _split_message(body, limit=4000)

    success = True
    for chunk in chunks:
        try:
            resp = httpx.post(
                f"{GRAPH_API}/{phone_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": chunk, "preview_url": True},
                },
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to send WhatsApp message to %s: %s", to, exc)
            success = False

    return success


def parse_incoming(payload: dict) -> list[dict]:
    """
    Parse a Meta webhook payload.
    Returns a list of message dicts: [{phone, text, wa_message_id}, ...]
    Only returns text messages (ignores media, reactions, etc.)
    """
    messages = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") != "text":
                        # Future: handle image/audio/etc
                        continue
                    messages.append(
                        {
                            "phone": msg["from"],
                            "text": msg["text"]["body"],
                            "wa_message_id": msg.get("id"),
                        }
                    )
    except Exception as exc:
        logger.error("Error parsing WhatsApp payload: %s", exc)
    return messages


def mark_read(message_id: str) -> None:
    """Mark an incoming message as read (shows double blue ticks)."""
    phone_id = get_phone_id()
    token = get_token()
    if not phone_id or not token:
        return
    try:
        httpx.post(
            f"{GRAPH_API}/{phone_id}/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
            timeout=5,
        )
    except Exception as exc:
        logger.debug("Could not mark message as read: %s", exc)


def _split_human(text: str) -> list[str]:
    """
    Split a bot response into 2–3 natural chunks that feel like
    a human sending separate messages rather than one wall of text.
    Splits on paragraph breaks; falls back to sentence boundaries.
    """
    text = text.strip()

    # Split on two or more newlines (paragraph breaks)
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    if len(paras) <= 1:
        # Single block — split at sentence boundary near the midpoint if long
        if len(text) <= 280:
            return [text]
        mid = len(text) // 2
        best = -1
        for pattern in (". ", "! ", "? ", "\n"):
            pos = text.rfind(pattern, 0, mid + 100)
            if pos > best:
                best = pos
        if best > 60:
            return [text[: best + 1].strip(), text[best + 1 :].strip()]
        return [text]

    if len(paras) <= 3:
        return paras

    # More than 3 paragraphs — group into exactly 3 chunks
    t1 = len(paras) // 3
    t2 = 2 * len(paras) // 3
    return [
        "\n\n".join(paras[:t1]),
        "\n\n".join(paras[t1:t2]),
        "\n\n".join(paras[t2:]),
    ]


def _split_message(text: str, limit: int = 4000) -> list[str]:
    """Split a long message into chunks that fit within WhatsApp's limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks

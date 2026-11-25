"""Typed conversation with a saved voice agent."""
import os

from openai import OpenAI

from app.voice_agents import instructions_for


def reply(agent, history: list[dict]) -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("The chat service is not configured.")
    messages = [{
        "role": "system",
        "content": instructions_for(agent) + (
            "\n\n# Typing\n"
            "The person is typing, not calling. Reply in plain English, in one or two short sentences. "
            "Use only the saved facts. If you do not know, offer to take a message."
        ),
    }]
    for item in history[-16:]:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        messages.append({
            "role": "assistant" if item.get("role") == "assistant" else "user",
            "content": text,
        })
    completion = OpenAI(api_key=key).chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=messages,
    )
    return (completion.choices[0].message.content or "").strip()

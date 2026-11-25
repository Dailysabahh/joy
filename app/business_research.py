"""Read a business website or a short description and draft an assistant."""
import ipaddress
import json
import os
import re
import socket
from urllib.parse import urlparse

import httpx
from openai import OpenAI

_TAG = re.compile(r"(?is)<(script|style|noscript).*?>.*?</\1>")
_HTML = re.compile(r"(?is)<[^>]+>")
_SPACE = re.compile(r"\s+")


def normalize_website(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in ("http", "https") or not host:
        raise ValueError("Enter a website like https://yourbusiness.com")
    if host in {"localhost"} or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("That website address can't be used.")
    _require_public_host(host)
    return url


def _require_public_host(host: str) -> None:
    try:
        ips = {host}
        ipaddress.ip_address(host)
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise ValueError("That website could not be found.") from exc
        ips = {info[4][0] for info in infos}
    for ip in ips:
        addr = ipaddress.ip_address(ip)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise ValueError("That website address can't be used.")


def fetch_website(url: str) -> str:
    safe = normalize_website(url)
    headers = {"User-Agent": "CloserTechAssistant/1.0"}
    with httpx.Client(timeout=12, follow_redirects=True, headers=headers) as client:
        response = client.get(safe)
        response.raise_for_status()
        final = urlparse(str(response.url))
        if final.hostname:
            _require_public_host(final.hostname)
        kind = (response.headers.get("content-type") or "").lower()
        if kind and "html" not in kind and "text" not in kind:
            raise ValueError("That page is not readable text.")
        raw = response.text[:350_000]
    text = _TAG.sub(" ", raw)
    text = _HTML.sub(" ", text)
    text = _SPACE.sub(" ", text).strip()
    if len(text) < 40:
        raise ValueError("The website opened, but there was almost no readable text.")
    return text[:12000]


def research_business(description: str, website: str) -> dict:
    words = (description or "").strip()
    site = (website or "").strip()
    page = ""
    source_note = ""
    if site:
        try:
            page = fetch_website(site)
            source_note = "Drafted from the website. Check it before you create the assistant."
        except Exception as exc:
            source_note = (
                "The website could not be read, so this draft uses only what you typed. "
                + str(exc)
            )
    if not words and not page:
        raise ValueError("Type a few words about the business, or add a website.")
    if not page and not source_note:
        source_note = "Drafted from what you typed. Nothing was fetched from the internet."

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("The research assistant is not configured yet.")
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You draft a voice receptionist for a business. "
                    "Use only the user's words and the website text. "
                    "Do not invent prices, addresses, phone numbers, staff names, or services "
                    "that are not in those sources. "
                    "Suggest a short human first name for the assistant. "
                    "Return JSON with keys: assistant_name, business_name, industry, role, "
                    "objective, summary, greeting, found, uncertain. "
                    "found and uncertain are arrays of short strings. "
                    "summary is one paragraph of facts the assistant can speak from, written about the business. "
                    "greeting is one short English sentence that says the assistant name and the business name, then asks how to help."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User's words:\n{words or '(none)'}\n\n"
                    f"Website:\n{site or '(none)'}\n\n"
                    f"Website text:\n{page or '(none)'}"
                ),
            },
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)
    profile = {
        "assistant_name": _text(data.get("assistant_name")) or "Amina",
        "business_name": _text(data.get("business_name")) or "the business",
        "industry": _text(data.get("industry")),
        "role": _text(data.get("role")) or "Receptionist",
        "objective": _text(data.get("objective")) or "Answer callers and help them take the next step.",
        "summary": _text(data.get("summary")),
        "greeting": _text(data.get("greeting")),
        "found": _list(data.get("found")),
        "uncertain": _list(data.get("uncertain")),
        "website": site,
        "source_note": source_note,
    }
    if not profile["summary"]:
        profile["summary"] = words or "The business details still need to be added."
    if not profile["greeting"]:
        profile["greeting"] = (
            f"Hello, this is {profile['assistant_name']} at {profile['business_name']}. How can I help?"
        )
    return profile


def _text(value) -> str:
    return str(value or "").strip()


def _list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:6]

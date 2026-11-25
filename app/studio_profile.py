"""Industry sections saved on a voice agent, and the facts it may say."""
import json
import re

PACKS = [
    {
        "id": "restaurant",
        "label": "Restaurant",
        "words": ("restaurant", "cafe", "café", "coffee", "bar", "bistro", "diner", "kitchen", "bakery", "food"),
        "sections": ("menu", "hours", "booking"),
        "functions": ("answer", "message", "prices", "reserve"),
    },
    {
        "id": "hotel",
        "label": "Hotel",
        "words": ("hotel", "lodge", "resort", "hostel", "inn", "motel", "guesthouse", "guest house"),
        "sections": ("rooms", "amenities", "policies"),
        "functions": ("answer", "message", "prices", "reserve"),
    },
    {
        "id": "clinic",
        "label": "Clinic",
        "words": ("clinic", "dental", "dentist", "doctor", "hospital", "medical", "pharmacy", "health", "therapy"),
        "sections": ("services", "people", "hours"),
        "people": "Practitioners",
        "functions": ("answer", "message", "prices", "reserve"),
    },
    {
        "id": "salon",
        "label": "Salon",
        "words": ("salon", "spa", "barber", "beauty", "nails"),
        "sections": ("services", "people", "hours"),
        "people": "Team",
        "functions": ("answer", "message", "prices", "reserve"),
    },
    {
        "id": "retail",
        "label": "Shop",
        "words": ("shop", "store", "retail", "boutique"),
        "sections": ("products", "hours", "policies"),
        "functions": ("answer", "message", "prices"),
    },
    {
        "id": "property",
        "label": "Property",
        "words": ("real estate", "property", "realtor"),
        "sections": ("listings", "hours", "policies"),
        "functions": ("answer", "message"),
    },
    {
        "id": "school",
        "label": "School",
        "words": ("school", "academy", "college", "university", "tutor"),
        "sections": ("programs", "hours", "faqs"),
        "functions": ("answer", "message"),
    },
]

GENERAL = {
    "id": "general",
    "label": "Business",
    "sections": ("services", "hours", "policies", "faqs"),
    "people": "People",
    "functions": ("answer", "message", "prices"),
}

FUNCTIONS = {
    "answer": "Answer from the saved information",
    "message": "Take a name and a number for a callback",
    "prices": "Quote only the prices saved here",
    "reserve": "Help the caller reserve, and say a person confirms it",
}

SECTIONS = {
    "menu": {
        "title": "Menu",
        "lead": "Dishes and drinks this assistant is allowed to mention.",
        "kind": "rows",
        "store": "menu",
        "fields": [
            ("name", "Item"),
            ("category", "Category"),
            ("description", "Description"),
            ("price", "Price"),
        ],
    },
    "rooms": {
        "title": "Rooms and rates",
        "lead": "Room types and the rates the assistant can quote.",
        "kind": "rows",
        "store": "rooms",
        "fields": [
            ("name", "Room"),
            ("occupancy", "Sleeps"),
            ("rate", "Rate"),
            ("description", "Details"),
        ],
    },
    "services": {
        "title": "Services",
        "lead": "What you offer, how long it takes, and the price.",
        "kind": "rows",
        "store": "services",
        "fields": [
            ("name", "Service"),
            ("duration", "Duration"),
            ("price", "Price"),
            ("description", "Details"),
        ],
    },
    "products": {
        "title": "Products",
        "lead": "What is for sale, and the price.",
        "kind": "rows",
        "store": "products",
        "fields": [
            ("name", "Product"),
            ("price", "Price"),
            ("description", "Details"),
        ],
    },
    "listings": {
        "title": "Listings",
        "lead": "Properties the assistant can describe.",
        "kind": "rows",
        "store": "listings",
        "fields": [
            ("name", "Listing"),
            ("price", "Price"),
            ("description", "Details"),
        ],
    },
    "programs": {
        "title": "Programs",
        "lead": "Courses or programs the assistant can explain.",
        "kind": "rows",
        "store": "programs",
        "fields": [
            ("name", "Program"),
            ("description", "Details"),
        ],
    },
    "people": {
        "title": "People",
        "lead": "Who the caller can ask for.",
        "kind": "rows",
        "store": "people",
        "fields": [
            ("name", "Name"),
            ("role", "Role"),
        ],
    },
    "hours": {"title": "Hours", "lead": "When you are open.", "kind": "text", "store": "hours"},
    "policies": {"title": "Policies", "lead": "Deposits, cancellation, and house rules.", "kind": "text", "store": "policies"},
    "amenities": {"title": "Amenities", "lead": "What the property includes.", "kind": "text", "store": "amenities"},
    "booking": {"title": "Reservations", "lead": "How a booking works, party size, and deposits.", "kind": "text", "store": "booking_notes"},
    "faqs": {"title": "Questions", "lead": "Short answers the assistant can give.", "kind": "faqs", "store": "faqs"},
}


def pack_for(source) -> dict:
    if hasattr(source, "industry"):
        text = " ".join(filter(None, [source.industry, source.business_name, getattr(source, "description", None)]))
    else:
        text = source or ""
    text = text.lower()
    for pack in PACKS:
        if any(re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) for word in pack["words"]):
            return pack
    return GENERAL


def _load(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def profile_of(agent) -> dict:
    raw = _load(getattr(agent, "profile", None))
    pack = pack_for(agent)
    profile = {
        "address": "",
        "public_phone": "",
        "hours": "",
        "policies": "",
        "amenities": "",
        "booking_notes": "",
        "menu": [],
        "rooms": [],
        "services": [],
        "products": [],
        "listings": [],
        "programs": [],
        "people": [],
        "faqs": [],
    }
    profile.update(raw)
    if "functions" not in raw:
        profile["functions"] = list(pack["functions"])
    return profile


def section_views(agent) -> list[dict]:
    pack = pack_for(agent)
    profile = profile_of(agent)
    views = []
    keys = list(pack["sections"])
    if "faqs" not in keys:
        keys.append("faqs")
    for key in keys:
        spec = dict(SECTIONS[key])
        if key == "people":
            spec["title"] = pack.get("people") or "People"
        spec["id"] = key
        if spec["kind"] == "text":
            spec["value"] = profile.get(spec["store"]) or ""
        else:
            spec["value"] = list(profile.get(spec["store"]) or []) + [{}, {}]
        views.append(spec)
    return views


def function_views(agent) -> list[dict]:
    pack = pack_for(agent)
    chosen = set(profile_of(agent).get("functions") or [])
    return [
        {"id": key, "label": FUNCTIONS[key], "on": key in chosen}
        for key in pack["functions"]
    ]


def _rows(form, store: str, fields: list[tuple[str, str]]) -> list[dict]:
    columns = {name: form.getlist(f"{store}_{name}") for name, _label in fields}
    length = max((len(values) for values in columns.values()), default=0)
    rows = []
    for index in range(length):
        row = {name: (values[index] if index < len(values) else "").strip() for name, values in columns.items()}
        if any(row.values()):
            rows.append(row)
    return rows


def apply_form(agent, form) -> None:
    from app.gemini_voices import normalize_manner, normalize_tone, normalize_voice

    section = str(form.get("section") or "")
    profile = profile_of(agent)
    if section == "identity":
        agent.name = str(form.get("name") or agent.name).strip() or agent.name
        agent.business_name = str(form.get("business_name") or agent.business_name).strip() or agent.business_name
        agent.role = str(form.get("role") or "").strip() or None
        agent.industry = str(form.get("industry") or "").strip() or None
        agent.website = str(form.get("website") or "").strip() or None
        agent.greeting = str(form.get("greeting") or agent.greeting).strip() or agent.greeting
        agent.voice = normalize_voice(str(form.get("voice") or agent.voice or ""))
        agent.tone = normalize_tone(str(form.get("tone") or agent.tone or ""))
        agent.manner = normalize_manner(str(form.get("manner") or agent.manner or ""))
        profile["address"] = str(form.get("address") or "").strip()
        profile["public_phone"] = str(form.get("public_phone") or "").strip()
    elif section == "knowledge":
        description = str(form.get("description") or "").strip()
        if description:
            agent.description = description
        agent.objective = str(form.get("objective") or "").strip() or None
    elif section == "functions":
        profile["functions"] = [item for item in form.getlist("functions") if item in FUNCTIONS]
    elif section in SECTIONS and SECTIONS[section]["kind"] == "text":
        profile[SECTIONS[section]["store"]] = str(form.get("body") or "").strip()
    elif section in SECTIONS and SECTIONS[section]["kind"] == "rows":
        spec = SECTIONS[section]
        profile[spec["store"]] = _rows(form, spec["store"], spec["fields"])
    elif section == "faqs":
        questions = form.getlist("faq_q")
        answers = form.getlist("faq_a")
        faqs = []
        for index, question in enumerate(questions):
            question = question.strip()
            answer = answers[index].strip() if index < len(answers) else ""
            if question or answer:
                faqs.append({"q": question, "a": answer})
        profile["faqs"] = faqs
    agent.profile = profile


def knowledge_text(agent) -> str:
    profile = profile_of(agent)
    lines = ["# Saved facts", "Use only these facts. If it is not here, say you will take a message. Do not invent items, rooms, or prices."]
    if profile.get("address"):
        lines.append(f"Address: {profile['address']}")
    if profile.get("public_phone"):
        lines.append(f"Public phone: {profile['public_phone']}")
    for key in ("hours", "policies", "amenities", "booking_notes"):
        if profile.get(key):
            lines.append(f"{key.replace('_', ' ').title()}: {profile[key]}")
    for store, title in (
        ("menu", "Menu"),
        ("rooms", "Rooms and rates"),
        ("services", "Services"),
        ("products", "Products"),
        ("listings", "Listings"),
        ("programs", "Programs"),
        ("people", "People"),
    ):
        rows = profile.get(store) or []
        if rows:
            lines.append(title + ":")
            for row in rows:
                bits = [str(value) for value in row.values() if value]
                if bits:
                    lines.append("- " + " · ".join(bits))
    for faq in profile.get("faqs") or []:
        if faq.get("q"):
            lines.append(f"Q: {faq.get('q')} A: {faq.get('a')}")
    allowed = [FUNCTIONS[key] for key in profile.get("functions") or [] if key in FUNCTIONS]
    if allowed:
        lines.append("Allowed on a call: " + "; ".join(allowed) + ".")
    return "\n".join(lines)

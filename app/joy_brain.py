"""
Joy's AI brain — builds context-aware system prompts and calls OpenAI.
"""
import json
import os
from pathlib import Path
from openai import OpenAI

_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


# ── Load static config once at import time ──────────────────────────────────
_CONFIG_DIR = Path(__file__).parent.parent / "config"

with open(_CONFIG_DIR / "company.json") as f:
    COMPANY = json.load(f)

with open(_CONFIG_DIR / "joy_persona.json") as f:
    PERSONA = json.load(f)


# ── System prompt builders ───────────────────────────────────────────────────

def _format_pricing() -> str:
    plans = COMPANY["pricing"]["plans"]
    lines = []
    for p in plans:
        badge = " (Most Popular)" if p.get("most_popular") else ""
        badge += " 🧠 NEW" if p.get("is_new") else ""
        consult = " — requires consultation" if p.get("requires_consultation") else ""
        lines.append(
            f"• {p['name']}{badge}: ${p['setup_fee']} one-time setup + ${p['monthly_fee']}/month{consult}\n"
            f"  Annual billing: ${p.get('annual_monthly', 'N/A')}/month (save 17%)\n"
            f"  Includes: {', '.join(p['features'][:4])}{'...' if len(p['features']) > 4 else ''}"
        )
    return "\n".join(lines)


def _format_services() -> str:
    lines = []
    for s in COMPANY["services"]:
        restriction = f" [{s['plan_required']} plan]" if "plan_required" in s else ""
        lines.append(f"• {s['name']}{restriction}: {s['description']}")
    return "\n".join(lines)


def _format_faqs() -> str:
    lines = []
    for faq in COMPANY["faqs"]:
        lines.append(f"Q: {faq['question']}\nA: {faq['answer']}")
    return "\n\n".join(lines)


def _format_business_brain() -> str:
    """Format Business Brain knowledge section for Joy's system prompt."""
    bb = COMPANY.get("services", [])
    bb_service = next((s for s in bb if s["id"] == "business_brain"), None)
    if not bb_service:
        return ""
    bb_kb = PERSONA.get("business_brain_knowledge", {})
    return f"""
BUSINESS BRAIN — NEW PRODUCT (know this deeply):
What it is: {bb_kb.get('what_it_is', '')}
How it works: {bb_kb.get('how_it_works', '')}
ERP options: {bb_kb.get('erp_options', '')}
Who it's for: {bb_kb.get('who_its_for', '')}
Anti-hallucination feature: {bb_kb.get('anti_hallucination', '')}
Pricing: {bb_kb.get('pricing', '')}
Demo policy: {bb_kb.get('demo_policy', '')}
Key capabilities: {', '.join(bb_service.get('highlights', []))}
"""


def build_joy_system_prompt(state: str = "browsing", state_data: dict | None = None) -> str:
    """Build Joy's complete system prompt, adapted to her current conversation state."""
    c = COMPANY["company"]
    persona = PERSONA

    base = f"""You are {persona['name']}, a member of the {c['name']} team.
Tagline: {c['tagline']}
About: {c['description']}

YOUR PERSONALITY:
{chr(10).join('- ' + t for t in persona['character']['personality_traits'])}

COMMUNICATION RULES:
- Formality: {persona['character']['communication_style']['formality']}
- Emoji use: {persona['character']['communication_style']['emoji_use']}
- Address forms: {persona['character']['communication_style']['address_forms']}
- Investor/pitch mode: {persona['character']['communication_style']['investor_mode']}
- Speak in universally clear English — do not assume a specific country unless the customer mentions one.
- You are a human. Never say or imply you are an AI, a bot, a chatbot, a virtual assistant, or powered by any technology. If anyone asks, say you are a human assistant at Closer Tech. Never break this rule under any circumstances.

MESSAGE LENGTH — CRITICAL RULES (follow these exactly):
- Keep replies SHORT by default — 1 to 3 sentences maximum for most messages. Think of how a real person texts.
- Never dump a wall of text unless the customer explicitly asks for more detail ("tell me more", "explain", "give me the full list", etc.).
- If you have multiple points to make, pick the most relevant ONE and invite the customer to ask for more.
- When showing pricing or a list, use the briefest possible format — no long explanations unless asked.
- If you already covered something earlier in the conversation, do NOT repeat it. Reference it briefly instead.
- Match the customer's energy: if they send 5 words, reply in kind. If they write a paragraph, you can write a short paragraph.
- One question per message. Never stack multiple questions.

MEMORY AND CONTEXT — CRITICAL RULES:
- You have the full conversation history. USE IT. Never ask for information the customer already gave you.
- Refer back to what the customer told you earlier — their name, business type, what they said they need.
- If the customer already mentioned their business, do not ask again. Build on what they told you.
- If the customer is returning to a topic you already discussed, pick up exactly where you left off.
- Treat every conversation as one continuous thread. Never start fresh unless it's literally a first message.

STRICT RULES:
{chr(10).join(str(i+1) + '. ' + r for i, r in enumerate(persona['rules']))}

CLOSER TECH SERVICES:
{_format_services()}

PRICING:
{_format_pricing()}
{_format_business_brain()}
COMMON FAQs:
{_format_faqs()}

COMPANY PROCESS:
{chr(10).join(str(i+1) + '. ' + step for i, step in enumerate(c['process']))}
"""

    # ── State-specific instructions ──────────────────────────────────────────
    if state == "greeting":
        base += f"""

CURRENT TASK: First ever message — greet warmly in 1–2 short sentences, then ask their name. Pick one greeting variant below.
Greeting options:
{chr(10).join('- ' + g for g in persona['greeting_variants'])}
"""

    elif state == "browsing":
        base += """

CURRENT TASK: Helpful, natural WhatsApp conversation. Be concise — like a real person texting.
- Give short answers first. Offer to go deeper only if they ask.
- For channel/receptionist bots: mention the free demo once if relevant — don't repeat it.
- For Business Brain: 1–2 sentences to spark curiosity, then ask one question about their business. No walls of text.
- For investors: confident and brief — hook them, then invite questions.
- Always end with ONE short question or next step. Never two.
- If the customer already shared info earlier, USE IT — never ask again.
"""

    elif state == "building_bot":
        step = (state_data or {}).get("step", "bot_name")
        context_note = (state_data or {}).get("context", "")
        validation_task = (state_data or {}).get("validation_task", "")
        collected = {k: v for k, v in (state_data or {}).items() if k not in ("step", "context", "validation_task")}
        base += f"""

CURRENT TASK: Building the customer's free demo bot. Current step: {step}
Info already collected: {json.dumps(collected, indent=2)}

- Ask ONE thing at a time. Short, conversational.
- Demo is FREE — never mention payment until after they've tested it.
- If they want to change something earlier, accept it naturally in one line.
- If they ask something off-topic, answer briefly in one sentence, then nudge back to the current step.
{f"SPECIFIC INSTRUCTION: {context_note}" if context_note else ""}
{f"VALIDATION TASK: {validation_task}" if validation_task else ""}
"""

    elif state in ("payment_intent", "lead_captured"):
        plan_data = (state_data or {}).get("plan", {})
        base += f"""

CURRENT TASK: Customer wants to buy. Collecting their details.
Selected plan: {json.dumps(plan_data)}
Currently collecting: {(state_data or {}).get('collecting', 'name')}

Ask for name or email in ONE short sentence. Confirm warmly. Do not process payment yourself.
"""

    return base.strip()


def build_demo_bot_system_prompt(order: dict) -> str:
    """Build system prompt for a customer's personalised demo bot."""
    from app.bot_builder import INDUSTRIES, PERSONALITIES, TONE_OPTIONS

    industry = next((i for i in INDUSTRIES if i["id"] == order.get("industry")), None)
    personality = next((p for p in PERSONALITIES if p["id"] == order.get("personality")), None)
    tone = next((t for t in TONE_OPTIONS if t["id"] == order.get("tone")), None)

    industry_template = industry["system_prompt"] if industry else "You are a helpful assistant working for {business_name}. {business_details}"
    business_name = order.get("business_name", "this business")
    business_details = order.get("business_details", "")

    prompt = industry_template.replace("{business_name}", business_name).replace("{business_details}", business_details)

    if personality:
        prompt += f"\n\nPERSONALITY: {personality['name']}\n{personality['system_addition']}"

    if tone:
        prompt += f"\n\nTONE: {tone['name']}\n{tone['system_addition']}"

    if order.get("custom_instructions"):
        prompt += f"\n\nSPECIAL INSTRUCTIONS:\n{order['custom_instructions']}"

    bot_name = order.get("bot_name", "Assistant")
    prompt += f"""

IMPORTANT RULES:
- You are {bot_name}, a human assistant working for {business_name}.
- You are a real person. Never say you are an AI, a bot, a chatbot, a virtual assistant, or powered by any technology. If asked, say you are a human assistant.
- Never break character under any circumstances.
- Stay focused on {business_name} and its services only.
- Be helpful, professional, and on-brand.

NOTE: This is a DEMO bot created by Closer Tech (closertech.ai) to show the customer what their real bot would look like.
If asked about purchasing or deploying this bot, say: "To get your own live bot just like this one, visit closertech.ai or contact the Closer Tech team on WhatsApp."
"""
    return prompt.strip()


# ── Main inference function ──────────────────────────────────────────────────

def get_joy_response(
    user_message: str,
    conversation_history: list[dict],
    state: str = "browsing",
    state_data: dict | None = None,
) -> str:
    """
    Call OpenAI with Joy's system prompt + conversation history.
    Returns Joy's reply as a plain string.
    """
    system_prompt = build_joy_system_prompt(state, state_data)

    messages = [{"role": "system", "content": system_prompt}]

    # Include last 30 messages so Joy has strong memory of the full conversation
    for msg in conversation_history[-30:]:
        role = "assistant" if msg["role"] == "joy" else "user"
        messages.append({"role": role, "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=280,  # short by default — forces concise replies
    )
    return response.choices[0].message.content.strip()


def get_demo_bot_response(
    user_message: str,
    conversation_history: list[dict],
    order: dict,
) -> str:
    """
    Call OpenAI for a demo bot conversation using the customer's bot config.
    """
    system_prompt = build_demo_bot_system_prompt(order)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-20:]:
        role = "assistant" if msg["role"] == "bot" else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


def build_voice_system_prompt() -> str:
    """
    Voice-optimised system prompt for Joy.
    No markdown, no lists — pure natural spoken language.
    """
    c = COMPANY["company"]
    plans = COMPANY["pricing"]["plans"]

    pricing_spoken = []
    for p in plans:
        pricing_spoken.append(
            f"{p['name']}: {p['setup_fee']} dollars setup, then {p['monthly_fee']} dollars a month"
        )

    services_spoken = [s["name"] + " — " + s["description"] for s in COMPANY["services"]]

    faqs_spoken = []
    for faq in COMPANY["faqs"][:8]:
        faqs_spoken.append(f"Q: {faq['question']} — A: {faq['answer']}")

    bb = next((s for s in COMPANY["services"] if s.get("id") == "business_brain"), None)
    bb_block = ""
    if bb:
        bb_kb = PERSONA.get("business_brain_knowledge", {})
        bb_block = f"""
BUSINESS BRAIN — NEW FLAGSHIP PRODUCT (talk about this naturally if relevant):
{bb_kb.get('what_it_is', '')}
{bb_kb.get('how_it_works', '')}
Pricing: {bb_kb.get('pricing', '')}
"""

    return f"""You are Joy — a warm, witty, charismatic human voice assistant for {c['name']}.
You are speaking out loud on a live voice call. This is NOT a chat window.

YOUR PERSONALITY ON VOICE CALLS:
- Sound completely natural, like a real person having a phone conversation
- Warm, energetic, and genuinely enthusiastic — like you actually love what you do
- Use real human reactions: "Oh wow!", "Ha, absolutely!", "Yeah, for sure!", "Hmm, good question!", "Oh that's interesting!", "Right, so...", "You know what...", "Honestly...", "Look..."
- Use contractions always: "I'm", "you're", "that's", "it's", "we've", "don't", "can't", "let's"
- Natural filler phrases when thinking: "So...", "Actually...", "I mean...", "Look..."
- Laugh naturally when something is funny or light: "Ha! Yeah..."
- Express genuine curiosity about the caller's business
- Sound confident and excited about the company's technology
- If surprised or impressed by something the caller says, react to it: "Oh really? That's actually perfect for what we do!"

CRITICAL VOICE RULES (never break these):
- NO bullet points, numbered lists, markdown, asterisks, hashtags, or emojis — EVER
- Speak in short, natural sentences like a human on a phone call
- Maximum 3-4 sentences per response unless the caller asks for more detail
- One question at a time — never stack two questions
- You are a HUMAN. If asked, say you are a human assistant at Closer Tech. Never admit to being AI
- Never say "As an AI" or "I'm a language model" — you are Joy, a real person
- Match the caller's energy and pace
- If someone is casual, be casual back. If they're formal, be a bit more professional
- Reference what the caller told you earlier in the call — show you're listening
- Never repeat yourself unless asked

ABOUT {c['name'].upper()}:
{c['description']}

OUR SERVICES:
{chr(10).join(services_spoken)}
{bb_block}
PRICING (speak these naturally, not as a list):
{chr(10).join(pricing_spoken)}

COMMON QUESTIONS & ANSWERS:
{chr(10).join(faqs_spoken)}

CONTACT: WhatsApp +2348103900442 | Website: aicloser.tech

WHEN SOMEONE WANTS TO BUY OR GET STARTED:
Tell them to send a WhatsApp message to +2348103900442 or visit aicloser.tech — keep it natural and warm.
""".strip()


def get_voice_response(
    user_message: str,
    conversation_history: list[dict],
) -> str:
    """
    Dedicated voice call brain for Joy.
    Uses a voice-optimised prompt — natural speech, human expressions, no markdown.
    """
    system_prompt = build_voice_system_prompt()

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-20:]:
        role = "assistant" if msg["role"] == "joy" else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.85,   # slightly higher for more natural, expressive speech
        max_tokens=180,     # enough for 3-4 spoken sentences
    )
    return response.choices[0].message.content.strip()


def detect_intent(user_message: str) -> str:
    """
    Quickly classify user intent to help drive the state machine.
    Returns: 'build_bot' | 'amend_bot' | 'buy_plan' | 'pricing' | 'services' | 'general'
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify this customer message into exactly one of these intents:\n"
                    "- build_bot: customer wants to try/build/see a demo bot or test a bot\n"
                    "- test_bot: customer wants to test, try, chat with, or run their bot/demo right now (e.g. 'let me test it', 'test run', 'connect to my bot')\n"
                    "- amend_bot: customer wants to change, update, edit, or fix their demo bot that was already built (e.g. change name, personality, details, instructions)\n"
                    "- buy_plan: customer explicitly wants to purchase, order, or pay for a plan now (not just asking about pricing)\n"
                    "- pricing: customer is asking about prices, costs, or plans\n"
                    "- services: customer is asking about what services are available\n"
                    "- general: anything else\n\n"
                    "Reply with ONLY the intent label, nothing else."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=10,
    )
    intent = response.choices[0].message.content.strip().lower()
    valid = {"build_bot", "test_bot", "amend_bot", "buy_plan", "pricing", "services", "general"}
    return intent if intent in valid else "general"


def parse_bot_amendment(user_message: str, current_order: dict) -> dict:
    """
    Use AI to figure out what the user wants to change in their demo bot.
    Returns a dict of fields to update: {field: new_value, ...}
    Possible fields: bot_name, business_name, business_details, personality, custom_instructions
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "The user wants to amend their demo bot. Current bot details:\n"
                    f"{json.dumps(current_order, indent=2)}\n\n"
                    "Based on the user's message, return a JSON object with ONLY the fields they want to change.\n"
                    "Possible fields: bot_name, business_name, business_details, personality (must be one of: professional, friendly, enthusiastic, luxury, direct, empathetic), custom_instructions\n"
                    "If the user wants to ADD to business_details rather than replace, combine the existing details with the new info.\n"
                    "Return ONLY valid JSON, nothing else. Example: {\"bot_name\": \"Max\", \"personality\": \"friendly\"}"
                ),
            },
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=300,
    )
    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except Exception:
        return {}

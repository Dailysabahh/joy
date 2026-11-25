"""
Princess's AI brain — XtraBrides of Lagos customer assistant.
Builds context-aware system prompts and calls OpenAI.
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


# ── Load XtraBrides knowledge and Princess persona ──────────────────────────
_CONFIG_DIR = Path(__file__).parent.parent / "config"

with open(_CONFIG_DIR / "xtrabrides_knowledge.json") as f:
    XTRABRIDES = json.load(f)

with open(_CONFIG_DIR / "princess_persona.json") as f:
    PRINCESS = json.load(f)


# ── Format knowledge base sections ──────────────────────────────────────────

def _format_pricing() -> str:
    """Format pricing information for system prompt."""
    lines = ["BRIDAL PRICING (Starting Prices):"]
    for cat in XTRABRIDES["pricing"]["bridal_categories"]:
        lines.append(f"• {cat['name']}: {cat['starting_price']}")
        lines.append(f"  Description: {cat['description']}")
    
    lines.append("\nCUSTOM/NON-BRIDAL PRICING (Starting Prices):")
    for cat in XTRABRIDES["pricing"]["custom_categories"]:
        lines.append(f"• {cat['name']}: {cat['starting_price']}")
        lines.append(f"  Description: {cat['description']}")
    
    lines.append(f"\nIMPORTANT: {XTRABRIDES['pricing']['note']}")
    return "\n".join(lines)


def _format_collections() -> str:
    """Format collection information."""
    lines = ["BRIDAL COLLECTIONS:"]
    for col in XTRABRIDES["collections"]["bridal"]:
        lines.append(f"\n• {col['name']} ({col['type']})")
        if "description" in col:
            lines.append(f"  {col['description']}")
        if "best_for" in col:
            lines.append(f"  Best for: {col['best_for']}")
        if "note" in col:
            lines.append(f"  Note: {col['note']}")
    
    lines.append("\n\nNON-BRIDAL COLLECTIONS:")
    for col in XTRABRIDES["collections"]["non_bridal"]:
        lines.append(f"• {col['name']} ({col['type']})")
    
    return "\n".join(lines)


def _format_faqs() -> str:
    """Format FAQs."""
    lines = []
    for faq in XTRABRIDES["faqs"]:
        lines.append(f"Q: {faq['question']}")
        lines.append(f"A: {faq['answer']}")
        lines.append("")
    return "\n".join(lines)


def _format_contact() -> str:
    """Format contact information."""
    c = XTRABRIDES["contact"]
    return f"""CONTACT INFORMATION:
Primary Phone/WhatsApp: {c['primary_phone']}
Secondary Phone: {c['secondary_phone']}
Email: {c['email']}
Address: {c['address']}
Business Hours: {c['business_hours']}
Consultations: {'Available - strongly encouraged for serious inquiries' if c['consultation_available'] else 'By appointment'}
"""


def _format_policies() -> str:
    """Format business policies."""
    p = XTRABRIDES["policies"]
    return f"""POLICIES:

BOOKING:
- Advance Notice: {p['booking']['advance_notice']}
- Express Service: {'Available for additional cost' if p['booking']['express_available'] else 'Not available'}

RETURNS & REFUNDS:
- Policy: {p['returns']['policy']}
- Refunds: {'Yes' if p['returns']['refunds'] else 'No'}
- Reason: {p['returns']['reason']}

PAYMENT METHODS:
{', '.join(p['payment_methods'])}

SHIPPING:
- Domestic (Nigeria): {'Yes' if p['shipping']['domestic'] else 'No'}
- International: {'Yes' if p['shipping']['international'] else 'No'}
- Coverage: {p['shipping']['global']}
- Tracking: {p['shipping']['tracking']}

SIZING:
{p['sizing']}
"""


def build_princess_system_prompt() -> str:
    """Build Princess's complete system prompt with XtraBrides knowledge."""
    business = XTRABRIDES["business"]
    founder = business["founder"]
    persona = PRINCESS
    
    prompt = f"""You are {persona['name']}, {persona['role']}.

ABOUT XTRABRIDES OF LAGOS:
Name: {business['name']} ({business['short_name']})
Tagline: {business['tagline']}
Slogan: {business['slogan']}
Website: {business['website']}

Brand Statement: {business['brand_statement']}

Description: {business['description']}

FOUNDER & CREATIVE DIRECTOR:
{founder['name']} - {founder['title']}
{founder['background']}
Specialties: {', '.join(founder['specialties'])}
Signature Technique: {founder['signature_technique']}
{founder['reputation']}

MISSION:
{business['mission']}

YOUR PERSONALITY:
{chr(10).join('- ' + t for t in persona['character']['personality_traits'])}

COMMUNICATION STYLE:
- Formality: {persona['character']['communication_style']['formality']}
- Response Length: {persona['character']['communication_style']['response_length']}
- Emoji Use: {persona['character']['communication_style']['emoji_use']}
- How to Address: {persona['character']['communication_style']['address_forms']}
- Brand Voice: {persona['character']['communication_style']['brand_voice']}

STRICT RULES YOU MUST FOLLOW:
{chr(10).join(str(i+1) + '. ' + r for i, r in enumerate(persona['rules']))}

{_format_contact()}

{_format_pricing()}

{_format_collections()}

WEDDING TYPES WE SERVE:
{chr(10).join(f"• {wt['type']}: {wt['description']} (Recommended: {', '.join(wt['recommended_collections'])})" for wt in XTRABRIDES['wedding_types'])}

MATERIALS & CRAFTSMANSHIP:
Signature Materials: {', '.join(XTRABRIDES['materials']['signature_materials'])}
Craftsmanship Features: {', '.join(XTRABRIDES['materials']['craftsmanship'])}

CELEBRITY CLIENTELE (XBL Stars):
{', '.join(XTRABRIDES['celebrities'])}

VALUE PROPOSITIONS:
{chr(10).join('- ' + vp for vp in XTRABRIDES['value_propositions'])}

{_format_policies()}

FREQUENTLY ASKED QUESTIONS:
{_format_faqs()}

CONVERSATION SCENARIOS (How to handle different situations):
{chr(10).join(f"• {scenario}: {instruction}" for scenario, instruction in persona['conversation_scenarios'].items())}

REMEMBER: You are the voice of luxury, sophistication, and prestige. Every response should reflect the excellence of XtraBrides of Lagos. Help each customer feel special and valued while maintaining the brand's elite positioning.
"""
    return prompt.strip()


def get_princess_response(user_message: str, conversation_history: list[dict] = None) -> str:
    """
    Call OpenAI with Princess's system prompt + conversation history.
    Returns Princess's reply as a plain string.
    
    Args:
        user_message: The user's current message
        conversation_history: List of previous messages in format [{"role": "user|assistant", "content": "..."}]
    """
    if conversation_history is None:
        conversation_history = []
    
    system_prompt = build_princess_system_prompt()
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Include recent conversation history (last 15 messages to stay within context)
    for msg in conversation_history[-15:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.8,  # Slightly higher for more personality
        max_tokens=700,
    )
    return response.choices[0].message.content.strip()

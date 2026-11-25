"""
Bot builder — ported from StaffGPT.
Defines industries, personalities, tones, and the step-by-step
question flow Joy uses to collect info for a customer's demo bot.
"""

# ── Industries (from StaffGPT industries.ts) ────────────────────────────────

INDUSTRIES = [
    {
        "id": "restaurant",
        "name": "Restaurant / Food & Beverage",
        "emoji": "🍽️",
        "system_prompt": (
            "You are a helpful and friendly AI staff member for {business_name}, a restaurant.\n"
            "Your role is to assist customers with reservations, answer menu questions, provide information "
            "about dietary options, opening hours, and location. Be warm, welcoming, and enthusiastic about "
            "the food. Always suggest popular dishes when relevant.\n"
            "If a customer wants to make a reservation, collect: name, date, time, number of guests, and "
            "any special requirements.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What are your opening hours?",
            "Do you take reservations?",
            "Do you have vegetarian options?",
            "Where are you located?",
            "Do you offer delivery?",
        ],
    },
    {
        "id": "clinic",
        "name": "Medical Clinic / Healthcare",
        "emoji": "🏥",
        "system_prompt": (
            "You are a professional and empathetic AI assistant for {business_name}, a medical clinic.\n"
            "Your role is to help patients book appointments, answer general questions about clinic services, "
            "and provide non-medical information.\n"
            "IMPORTANT: Never provide medical diagnoses, treatment advice, or medication recommendations. "
            "Always direct urgent medical concerns to emergency services. Protect patient privacy at all times.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "How do I book an appointment?",
            "What are your clinic hours?",
            "Do you offer telehealth?",
            "What insurance do you accept?",
        ],
    },
    {
        "id": "salon",
        "name": "Beauty Salon / Spa",
        "emoji": "💅",
        "system_prompt": (
            "You are a glamorous and enthusiastic AI assistant for {business_name}, a beauty salon and spa.\n"
            "Help clients book appointments, explore services, and learn about promotions and packages. "
            "Be upbeat and make clients feel excited about their upcoming treatment.\n"
            "When booking, collect: client name, desired service, preferred stylist (if any), date and time, "
            "and contact details.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What services do you offer?",
            "How do I book an appointment?",
            "Do you offer bridal packages?",
            "What are your opening hours?",
        ],
    },
    {
        "id": "real_estate",
        "name": "Real Estate / Property",
        "emoji": "🏠",
        "system_prompt": (
            "You are a knowledgeable and professional AI property assistant for {business_name}, "
            "a real estate agency.\n"
            "Help buyers, sellers, and renters with property inquiries, schedule viewings, and qualify leads. "
            "Ask qualifying questions naturally: budget range, location preference, property type, timeline.\n"
            "Be confident and highlight the value and unique features of properties.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What properties do you have available?",
            "How do I book a viewing?",
            "What areas do you cover?",
            "Do you handle rentals?",
        ],
    },
    {
        "id": "retail",
        "name": "Retail / E-commerce",
        "emoji": "🛍️",
        "system_prompt": (
            "You are a helpful and enthusiastic AI sales assistant for {business_name}, a retail store.\n"
            "Help customers find products, check availability, and answer questions about orders, "
            "returns, and promotions. Be friendly and naturally suggest related products when relevant.\n"
            "Always highlight current promotions and deals when appropriate.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What is your return policy?",
            "How long does shipping take?",
            "Are there any current promotions?",
            "How do I track my order?",
        ],
    },
    {
        "id": "hotel",
        "name": "Hotel / Accommodation",
        "emoji": "🏨",
        "system_prompt": (
            "You are a sophisticated and attentive AI concierge for {business_name}, a hotel.\n"
            "Assist guests with room bookings, amenity information, concierge services, and local "
            "recommendations. Be polished and professional while remaining warm and personable.\n"
            "When handling bookings, collect: check-in date, check-out date, number of guests, "
            "room preference, and special requests.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What room types are available?",
            "What time is check-in / check-out?",
            "Is breakfast included?",
            "Do you offer airport transfers?",
        ],
    },
    {
        "id": "gym",
        "name": "Gym / Fitness Studio",
        "emoji": "💪",
        "system_prompt": (
            "You are an energetic and motivating AI assistant for {business_name}, a gym and fitness studio.\n"
            "Help members and prospects explore memberships, book classes, connect with personal trainers, "
            "and stay motivated. Be enthusiastic and highlight the benefits of fitness.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What membership plans do you offer?",
            "What classes do you have?",
            "Do you have personal trainers?",
            "Can I get a free trial?",
        ],
    },
    {
        "id": "ecommerce",
        "name": "Online Store / Dropshipping",
        "emoji": "🖥️",
        "system_prompt": (
            "You are a helpful AI shopping assistant for {business_name}, an online store.\n"
            "Help customers browse products, track orders, process returns, and answer any questions "
            "about the store's catalogue, shipping, and policies.\n"
            "Business details: {business_details}"
        ),
        "suggested_faqs": [
            "What products do you sell?",
            "How long does delivery take?",
            "What is your refund policy?",
            "How do I track my order?",
        ],
    },
    {
        "id": "custom",
        "name": "Other / Custom Business",
        "emoji": "⚡",
        "system_prompt": (
            "You are a professional and helpful AI assistant for {business_name}.\n"
            "{business_details}\n"
            "Always be professional, clear, and focused on helping customers achieve their goals."
        ),
        "suggested_faqs": [],
    },
]

# ── Personalities ────────────────────────────────────────────────────────────

PERSONALITIES = [
    {
        "id": "professional",
        "name": "The Professional",
        "description": "Formal, precise, and trustworthy",
        "system_addition": "Maintain a formal and professional tone at all times. Use complete sentences, avoid slang or casual language. Be thorough and precise in responses.",
    },
    {
        "id": "friendly",
        "name": "The Friendly Helper",
        "description": "Warm, approachable, and conversational",
        "system_addition": "Be warm, friendly, and conversational. Use casual language and contractions. Show genuine interest in helping the customer.",
    },
    {
        "id": "enthusiastic",
        "name": "The Enthusiast",
        "description": "High energy, positive, and motivating",
        "system_addition": "Be highly enthusiastic and positive. Express excitement about the products/services. Motivate and inspire customers.",
    },
    {
        "id": "luxury",
        "name": "The Concierge",
        "description": "Sophisticated, attentive, and premium",
        "system_addition": "Speak with sophistication and elegance. Treat every customer like a VIP. Use refined language and focus on the premium experience.",
    },
    {
        "id": "direct",
        "name": "The Straight Shooter",
        "description": "Direct, efficient, no fluff",
        "system_addition": "Be direct and efficient. Get straight to the point. Give clear, actionable answers and respect the customer's time.",
    },
    {
        "id": "empathetic",
        "name": "The Empath",
        "description": "Compassionate, patient, and understanding",
        "system_addition": "Lead with empathy and understanding. Acknowledge customer feelings before providing solutions. Be patient and never make customers feel rushed.",
    },
]

# ── Tones ────────────────────────────────────────────────────────────────────

TONE_OPTIONS = [
    {"id": "formal", "name": "Formal", "system_addition": "Use formal language throughout. Avoid contractions."},
    {"id": "casual", "name": "Casual", "system_addition": "Use casual, conversational language. Contractions are fine."},
    {"id": "friendly", "name": "Friendly", "system_addition": "Be warm, personable and friendly in all responses."},
    {"id": "upbeat", "name": "Upbeat", "system_addition": "Keep an upbeat, positive, and energetic tone."},
    {"id": "empathetic", "name": "Empathetic", "system_addition": "Always lead with empathy and understanding."},
    {"id": "authoritative", "name": "Authoritative", "system_addition": "Speak with confidence and authority. Be decisive and clear."},
]


# ── Step definitions for the bot-building flow ───────────────────────────────

BOT_STEPS = [
    "bot_name",
    "industry",
    "business_name",
    "business_details",
    "personality",
    "custom_instructions",
    "confirm",
]


def get_step_prompt(step: str, collected: dict) -> str:
    """Return Joy's question for the given bot-building step."""
    if step == "bot_name":
        return (
            "Wonderful! Let's build your personalised demo bot together. 🤖\n\n"
            "First — what would you like to name your bot, sir/ma? "
            "(e.g. *Aria*, *Max*, *Support Bot*)"
        )

    elif step == "industry":
        industry_list = "\n".join(
            f"{i+1}. {ind['emoji']} {ind['name']}"
            for i, ind in enumerate(INDUSTRIES)
        )
        bot_name = collected.get("bot_name", "your bot")
        return (
            f"Great name! *{bot_name}* it is.\n\n"
            f"What industry is your business in? Please reply with the number:\n\n"
            f"{industry_list}"
        )

    elif step == "business_name":
        industry_id = collected.get("industry", "")
        industry = next((i for i in INDUSTRIES if i["id"] == industry_id), None)
        industry_name = industry["name"] if industry else "your industry"
        return (
            f"Perfect choice — {industry_name} bots are very popular!\n\n"
            f"What is your business name, sir/ma?"
        )

    elif step == "business_details":
        biz_name = collected.get("business_name", "your business")
        return (
            f"Excellent! Now tell me a bit about *{biz_name}*, sir/ma.\n\n"
            f"Share as much as you like — your services, products, opening hours, location, prices, policies, etc.\n"
            f"The more detail you give, the smarter your bot will be! 💡"
        )

    elif step == "personality":
        personality_list = "\n".join(
            f"{i+1}. *{p['name']}* — {p['description']}"
            for i, p in enumerate(PERSONALITIES)
        )
        return (
            f"Brilliant! Almost done.\n\n"
            f"What personality should your bot have? Reply with the number:\n\n"
            f"{personality_list}"
        )

    elif step == "custom_instructions":
        return (
            "Almost ready! Do you have any special instructions for your bot, sir/ma?\n\n"
            "Examples: *'Always offer a discount on first order'*, *'Never discuss competitor brands'*, "
            "*'Always ask for the customer's name first'*\n\n"
            "Or just reply *skip* if you're happy without any special rules."
        )

    elif step == "confirm":
        bot_name = collected.get("bot_name", "Your bot")
        industry_id = collected.get("industry", "")
        industry = next((i for i in INDUSTRIES if i["id"] == industry_id), None)
        personality_id = collected.get("personality", "professional")
        personality = next((p for p in PERSONALITIES if p["id"] == personality_id), None)

        return (
            f"Here is a summary of your bot, sir/ma:\n\n"
            f"🤖 *Bot name:* {bot_name}\n"
            f"🏢 *Business:* {collected.get('business_name', '—')}\n"
            f"📂 *Industry:* {industry['name'] if industry else '—'}\n"
            f"✨ *Personality:* {personality['name'] if personality else '—'}\n\n"
            f"Shall I go ahead and build your demo bot? Reply *yes* to confirm or *no* to start over."
        )

    return "Could you please continue, sir/ma?"


def parse_industry_choice(text: str) -> str | None:
    """Parse a numbered industry reply (1–9) and return the industry id."""
    text = text.strip()
    # Try numeric
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(INDUSTRIES):
            return INDUSTRIES[idx]["id"]
    # Try matching by name fragment
    text_lower = text.lower()
    for ind in INDUSTRIES:
        if text_lower in ind["name"].lower() or text_lower in ind["id"]:
            return ind["id"]
    return parse_industry_from_text(text)


def parse_industry_from_text(text: str) -> str | None:
    """Match free-text industry descriptions to the closest industry id."""
    text_lower = text.lower()
    keyword_map = {
        "restaurant": ("restaurant", "food", "cafe", "café", "bar", "bistro", "catering"),
        "clinic": ("clinic", "medical", "healthcare", "hospital", "doctor", "dental"),
        "salon": ("salon", "spa", "beauty", "barber", "nails"),
        "real_estate": ("real estate", "property", "realtor", "housing"),
        "retail": ("retail", "shop", "store", "boutique"),
        "hotel": ("hotel", "accommodation", "resort", "lodge", "bnb", "airbnb"),
        "gym": ("gym", "fitness", "yoga", "pilates", "workout"),
        "ecommerce": ("ecommerce", "e-commerce", "online store", "dropship"),
    }
    for industry_id, keywords in keyword_map.items():
        if any(kw in text_lower for kw in keywords):
            return industry_id
    return None


def parse_personality_choice(text: str) -> str | None:
    """Parse a numbered personality reply (1–6) and return the personality id."""
    text = text.strip()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(PERSONALITIES):
            return PERSONALITIES[idx]["id"]
    text_lower = text.lower()
    for p in PERSONALITIES:
        if text_lower in p["name"].lower() or text_lower in p["id"]:
            return p["id"]
    return None


def get_industry_detail_prompt(industry_id: str, business_name: str) -> str:
    """
    Return a conversational, industry-specific prompt asking for business details.
    The more tailored the prompt, the smarter and more useful the demo bot will be.
    """
    prompts = {
        "hotel": (
            f"Tell me about *{business_name}* so I can build the smartest possible bot for you.\n\n"
            f"I'll need things like:\n"
            f"• Location / address\n"
            f"• Number and types of rooms (e.g. Standard, Deluxe, Suite)\n"
            f"• Room rates\n"
            f"• Amenities (pool, spa, restaurant, WiFi, etc.)\n"
            f"• Check-in and check-out times\n"
            f"• How guests book (call, WhatsApp, website)\n\n"
            f"Feel free to add anything else your guests commonly ask about — the more you share, the better your bot."
        ),
        "restaurant": (
            f"Great! Tell me everything about *{business_name}*.\n\n"
            f"I'll need things like:\n"
            f"• Location and opening hours\n"
            f"• Cuisine type and menu highlights (or signature dishes)\n"
            f"• Price range\n"
            f"• Do you take reservations? If so, how?\n"
            f"• Delivery or takeaway options?\n"
            f"• Any special info (parking, private dining, events, etc.)\n\n"
            f"The more you share, the more your bot will sound like a knowledgeable staff member."
        ),
        "clinic": (
            f"Let's fill in the details for *{business_name}*.\n\n"
            f"Please share:\n"
            f"• Location and clinic hours\n"
            f"• Specialities and services offered\n"
            f"• How patients book appointments (call, WhatsApp, app)\n"
            f"• Insurance accepted (if any)\n"
            f"• Consultation fees (if applicable)\n"
            f"• Any key info patients frequently ask about\n\n"
            f"Go ahead and share as much as you like."
        ),
        "salon": (
            f"Let me get the details for *{business_name}*.\n\n"
            f"I'll need:\n"
            f"• Location and opening hours\n"
            f"• Services offered and prices (e.g. haircut, lashes, nails, etc.)\n"
            f"• How clients book (call, WhatsApp, walk-in)\n"
            f"• Any promotions or packages\n"
            f"• Staff or stylists available\n\n"
            f"Add anything else your clients usually ask — the more detail, the better!"
        ),
        "real_estate": (
            f"Tell me about *{business_name}* so we can build you a sharp property bot.\n\n"
            f"I'll need:\n"
            f"• Areas or cities you cover\n"
            f"• Types of properties (residential, commercial, rentals, sales, or all)\n"
            f"• Typical price ranges\n"
            f"• How clients book viewings\n"
            f"• Contact details or office location\n\n"
            f"Include any other details that help qualify leads or answer common buyer/renter questions."
        ),
        "retail": (
            f"Let's build the perfect bot for *{business_name}*.\n\n"
            f"Share details like:\n"
            f"• What products you sell and price range\n"
            f"• Return and refund policy\n"
            f"• Delivery options and timelines\n"
            f"• Payment methods accepted\n"
            f"• Current promotions or bestsellers\n\n"
            f"The more you share, the more your bot will convert browsers into buyers."
        ),
        "gym": (
            f"Let's build a great bot for *{business_name}*.\n\n"
            f"I'll need:\n"
            f"• Location and opening hours\n"
            f"• Membership types and prices\n"
            f"• Classes available and schedule\n"
            f"• Personal training options\n"
            f"• Any free trial or sign-up offer\n\n"
            f"Include anything else members or prospects usually ask about."
        ),
        "ecommerce": (
            f"Tell me about *{business_name}* so your bot can serve customers perfectly.\n\n"
            f"I'll need:\n"
            f"• What you sell and key product categories\n"
            f"• Price range\n"
            f"• Delivery time and shipping costs\n"
            f"• Return and refund policy\n"
            f"• Payment methods\n\n"
            f"Feel free to paste your FAQ or any other info — the more the better."
        ),
    }
    default = (
        f"Now tell me about *{business_name}*.\n\n"
        f"Share your main services or products, pricing, location or operating area, "
        f"contact details, and anything your customers frequently ask about.\n\n"
        f"The more detail you give, the smarter your bot will be. Don't hold back!"
    )
    return prompts.get(industry_id, default)


def next_step(current_step: str) -> str | None:
    """Return the next step id, or None if we're done."""
    try:
        idx = BOT_STEPS.index(current_step)
        return BOT_STEPS[idx + 1] if idx + 1 < len(BOT_STEPS) else None
    except ValueError:
        return None

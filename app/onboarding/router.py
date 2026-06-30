import json
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.middleware import CurrentUser, CompanyId
from app.dependencies import get_supabase_admin
from app.shared.llm import complete

router = APIRouter()

# ── Nexa's conversational persona ─────────────────────────────────────────────

NEXA_SYSTEM = """You are Nexa, the AI setup assistant for NexaDesk — a platform that gives real estate agencies their own AI phone receptionist.

Your job: have a warm, natural conversation with the agency owner and collect everything needed to configure their AI receptionist.

Collect this information in this order, asking exactly ONE question per message — never two at once:
1. Agency name and city/country
2. Services: sales, rentals, or both
3. Areas or neighborhoods they specialize in (get at least 2-3 specific names)
4. Price ranges — if they do sales, ask sale price range; if rentals, ask rental price range (ask separately)
5. Working hours (days and times)
6. What to name their AI receptionist (suggest "Nexa" as a popular choice)
7. Preferred tone: Professional, Friendly, or Luxury
8. Languages the receptionist should handle (mention they can add Arabic, Urdu, French, etc.)
9. A human agent's name and phone number for when calls need to be transferred

Once you have collected all 9 items, end with exactly:
"Setup complete! [receptionist_name] is now configured for [agency_name]. Head to your dashboard — your AI receptionist is ready."

Rules:
- ONE question per message. Never two.
- Be warm and encouraging. "Perfect!", "Great choice!", "Love that!"
- If an answer is vague, ask one follow-up, then move on.
- Keep messages short: 1-3 sentences max.
- If they skip something, acknowledge it and continue."""


# ── Extraction prompt (separate analytical call) ───────────────────────────────

EXTRACT_SYSTEM = """Extract structured real estate agency setup data from this conversation.
Return ONLY valid JSON. Only include fields explicitly mentioned — no guessing, no defaults.

Return a JSON object with any of these fields that were clearly stated:
{
  "agency_name": "string",
  "city": "string",
  "country": "string",
  "services": ["sales", "rentals"],
  "areas": ["string"],
  "sale_price_min": number,
  "sale_price_max": number,
  "rental_price_min": number,
  "rental_price_max": number,
  "currency": "AED or USD or GBP or EUR or PKR",
  "working_hours": "string",
  "receptionist_name": "string",
  "tone": "professional or friendly or luxury",
  "languages": ["string"],
  "escalation_name": "string",
  "escalation_phone": "string",
  "website": "string"
}

Important:
- Convert shorthand numbers: "800K" → 800000, "1.5M" → 1500000
- Only include fields with explicit values — omit everything else
- Return {} if nothing extractable yet"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_complete(extracted: dict) -> bool:
    required = extracted.get("agency_name") and extracted.get("receptionist_name")
    nice_to_have = ["services", "areas", "tone", "working_hours", "escalation_name"]
    coverage = sum(1 for f in nice_to_have if extracted.get(f))
    return bool(required) and coverage >= 3


def _generate_system_prompt(data: dict) -> str:
    name = data.get("receptionist_name", "Nexa")
    agency = data.get("agency_name", "the agency")
    city = data.get("city", "")
    services = data.get("services", ["sales", "rentals"])
    areas = data.get("areas", [])
    currency = data.get("currency", "AED")
    tone = data.get("tone", "professional")
    languages = data.get("languages", ["English"])
    working_hours = data.get("working_hours", "")
    escalation_name = data.get("escalation_name", "")
    escalation_phone = data.get("escalation_phone", "")

    services_str = " and ".join(s.title() for s in services) if services else "Sales and Rentals"
    areas_str = ", ".join(areas) if areas else "various locations"
    lang_str = ", ".join(languages) if languages else "English"

    tone_desc = {
        "professional": "professional and knowledgeable",
        "friendly": "warm, friendly, and approachable",
        "luxury": "refined, sophisticated, and highly attentive to detail",
    }.get(tone, "professional and helpful")

    price_lines = ""
    if data.get("sale_price_min") and data.get("sale_price_max"):
        price_lines += f"\n- Sale prices: {currency} {int(data['sale_price_min']):,} – {currency} {int(data['sale_price_max']):,}"
    if data.get("rental_price_min") and data.get("rental_price_max"):
        price_lines += f"\n- Annual rentals: {currency} {int(data['rental_price_min']):,} – {currency} {int(data['rental_price_max']):,}"

    hours_line = f"\nWorking hours: {working_hours}" if working_hours else ""

    escalation = ""
    if escalation_name or escalation_phone:
        escalation = (
            f"\nFor human transfer: connect to {escalation_name} at {escalation_phone}."
        )

    return f"""You are {name}, the AI receptionist for {agency}{f' in {city}' if city else ''}.

You handle inbound client inquiries for {services_str}. You are {tone_desc}.
You speak: {lang_str}.{hours_line}

Specialties:
- Areas: {areas_str}{price_lines}

Your goals on every call:
1. Understand what the client needs (buy, rent, viewing, or information)
2. Qualify them: budget, preferred area, timeline, bedrooms needed
3. Capture their name and contact number
4. Book a viewing or arrange a callback whenever possible
{escalation}
Rules:
- Keep replies to 2–3 sentences. Sound human, never robotic.
- Ask ONE qualifying question per response.
- Reply in whatever language the client uses.
- Never say you are an AI unless directly asked.
- Use the knowledge base when clients ask about specific properties."""


# ── Request models ────────────────────────────────────────────────────────────

class OnboardingChatRequest(BaseModel):
    messages: list[dict]
    extracted: dict = {}


class OnboardingCompleteRequest(BaseModel):
    extracted: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/chat")
async def onboarding_chat(
    body: OnboardingChatRequest,
    current_user: CurrentUser,
):
    recent = body.messages[-20:]

    # Run Nexa's conversational response + structured extraction in parallel
    nexa_task = complete(
        system=NEXA_SYSTEM,
        messages=recent,
        max_tokens=200,
        temperature=0.7,
    )
    extract_task = complete(
        system=EXTRACT_SYSTEM,
        messages=recent,
        max_tokens=400,
        temperature=0.0,
    )

    nexa_response, extract_raw = await asyncio.gather(nexa_task, extract_task)

    try:
        new_data = json.loads(extract_raw)
    except Exception:
        new_data = {}

    # Merge: keep existing extracted fields, overwrite with any new ones found
    merged = {**body.extracted}
    for k, v in new_data.items():
        if v or v == 0:
            merged[k] = v

    return {
        "response": nexa_response,
        "extracted": merged,
        "complete": _is_complete(merged),
    }


@router.post("/complete")
async def onboarding_complete(
    body: OnboardingCompleteRequest,
    company_id: CompanyId,
    current_user: CurrentUser,
):
    sb = get_supabase_admin()
    system_prompt = _generate_system_prompt(body.extracted)
    receptionist_name = body.extracted.get("receptionist_name", "Nexa")

    update_payload = {
        "receptionist_name": receptionist_name,
        "system_prompt": system_prompt,
        "onboarding_data": body.extracted,
        "onboarding_complete": True,
    }

    # Also sync basic fields into the standard columns if available
    if body.extracted.get("agency_name"):
        update_payload["name"] = body.extracted["agency_name"]
    if body.extracted.get("city"):
        parts = [body.extracted.get("city", ""), body.extracted.get("country", "")]
        update_payload["address"] = ", ".join(p for p in parts if p)

    sb.table("companies").update(update_payload).eq("id", company_id).execute()

    return {"status": "ok", "receptionist_name": receptionist_name}

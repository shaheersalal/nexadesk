"""
Seed Houston-area demo data for Pinnacle Property Management into Supabase and Qdrant.

Run once (idempotent — safe to re-run):
    conda activate nexa
    python scripts/seed_demo.py

Requires .env to be populated (SUPABASE_*, EMBED_API_KEY, QDRANT_*).
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.properties.models import property_to_text

settings = get_settings()

EMBED_ENABLED = bool(os.getenv("EMBED_API_KEY", "").strip())
if EMBED_ENABLED:
    from app.rag.pipeline import ingest_text
else:
    async def ingest_text(*args, **kwargs):
        pass  # no-op when EMBED_API_KEY is not set

# ── Demo company ──────────────────────────────────────────────────────────────

DEMO_COMPANY = {
    "name": "Pinnacle Property Management",
    "phone": "+18324550192",
    "email": "hello@pinnaclehouston.demo",
    "address": "3800 Montrose Blvd, Suite 200, Houston, TX 77006",
    "ai_persona": (
        "a friendly, knowledgeable Houston real estate specialist who knows every "
        "neighborhood from Sugar Land to The Woodlands, always makes callers feel at "
        "home, and speaks warmly whether in English or Spanish"
    ),
    "working_hours": {
        "Mon-Fri": "8:00-18:00",
        "Sat": "9:00-15:00",
        "Sun": "closed",
    },
}

# ── Houston-area properties ───────────────────────────────────────────────────

DEMO_PROPERTIES = [
    {
        "title": "Midtown Modern Townhome",
        "address": "2714 Brazos St",
        "city": "Houston",
        "state": "TX",
        "zip": "77006",
        "property_type": "townhouse",
        "bedrooms": 3,
        "bathrooms": 3.5,
        "sqft": 2100,
        "price": 489_000,
        "status": "active",
        "description": (
            "Sleek 3-story townhome in the heart of Midtown. Open-concept living on the "
            "second floor, rooftop terrace with city skyline views, quartz countertops, "
            "Bosch appliances, and a private 2-car garage. Walk to restaurants on Main St "
            "and the Midtown Greenway trail. No HOA."
        ),
        "features": [
            "rooftop terrace", "city views", "2-car garage", "no HOA",
            "quartz countertops", "walkable", "new construction",
        ],
        "mls_number": "HAR-2024-001",
    },
    {
        "title": "Sugar Land Family Home — First Colony",
        "address": "4821 Commonwealth Blvd",
        "city": "Sugar Land",
        "state": "TX",
        "zip": "77479",
        "property_type": "house",
        "bedrooms": 4,
        "bathrooms": 3.0,
        "sqft": 2950,
        "price": 565_000,
        "status": "active",
        "description": (
            "Well-maintained 4-bedroom in the coveted First Colony master-planned community. "
            "Formal dining, large game room, updated kitchen with granite and stainless appliances, "
            "and a covered back patio overlooking the greenbelt. Zoned to top-rated Fort Bend ISD "
            "schools. Community pool, tennis, and walking trails."
        ),
        "features": [
            "greenbelt lot", "Fort Bend ISD", "community pool", "game room",
            "granite kitchen", "covered patio", "cul-de-sac street",
        ],
        "mls_number": "HAR-2024-002",
    },
    {
        "title": "Heights Craftsman Bungalow",
        "address": "1206 Harvard St",
        "city": "Houston",
        "state": "TX",
        "zip": "77008",
        "property_type": "house",
        "bedrooms": 3,
        "bathrooms": 2.0,
        "sqft": 1780,
        "price": 595_000,
        "status": "active",
        "description": (
            "Lovingly restored 1930s craftsman on a tree-lined Heights street. Original "
            "hardwood floors, updated kitchen with farmhouse sink, clawfoot tub in the "
            "primary bath, and a screened back porch. Large backyard with fruit trees. "
            "Steps from the Heights Hike & Bike Trail and White Oak Music Hall."
        ),
        "features": [
            "original hardwood floors", "Heights Trail access", "screened porch",
            "restored craftsman", "large backyard", "historic charm",
        ],
        "mls_number": "HAR-2024-003",
    },
    {
        "title": "Katy New Construction — Cinco Ranch",
        "address": "23410 Sorrel Mist Dr",
        "city": "Katy",
        "state": "TX",
        "zip": "77494",
        "property_type": "house",
        "bedrooms": 5,
        "bathrooms": 4.0,
        "sqft": 3400,
        "price": 649_000,
        "status": "active",
        "description": (
            "Brand-new 2-story in Cinco Ranch with 3-car garage and full smart-home package. "
            "Chef's kitchen with 36\" gas range, butler's pantry, and oversized island. Primary "
            "suite down, 4 bedrooms up with ensuite baths. Extended covered patio and full "
            "outdoor kitchen. Katy ISD — rated among the best in Texas."
        ),
        "features": [
            "new construction", "3-car garage", "smart home", "chef kitchen",
            "Katy ISD", "outdoor kitchen", "butler's pantry", "5 bedrooms",
        ],
        "mls_number": "HAR-2024-004",
    },
    {
        "title": "EaDo Live-Work Loft",
        "address": "2401 Commerce St #310",
        "city": "Houston",
        "state": "TX",
        "zip": "77003",
        "property_type": "condo",
        "bedrooms": 1,
        "bathrooms": 1.0,
        "sqft": 1050,
        "price": 285_000,
        "status": "active",
        "description": (
            "Industrial-chic loft in a converted East Downtown warehouse. Exposed brick, "
            "16-ft ceilings, polished concrete floors, and oversized windows flooding the "
            "space with natural light. Building has a rooftop dog run, co-working lounge, "
            "and secured parking. Steps from East End bars and walking distance to Minute "
            "Maid Park."
        ),
        "features": [
            "exposed brick", "16-ft ceilings", "polished concrete", "rooftop dog run",
            "co-working lounge", "EaDo location", "Minute Maid Park walkable",
        ],
        "mls_number": "HAR-2024-005",
    },
    {
        "title": "Pearland Executive Home",
        "address": "3215 Shadow Creek Dr",
        "city": "Pearland",
        "state": "TX",
        "zip": "77584",
        "property_type": "house",
        "bedrooms": 4,
        "bathrooms": 3.5,
        "sqft": 3200,
        "price": 525_000,
        "status": "active",
        "description": (
            "Elegant 4-bedroom in Shadow Creek Ranch. Rotunda entry, vaulted ceilings, "
            "study with built-ins, and a chef's kitchen open to the family room. Resort-style "
            "backyard with pool, spa, and cabana. Pearland ISD, low taxes, and close to the "
            "Texas Medical Center. Easy 288 commute to downtown."
        ),
        "features": [
            "pool and spa", "Shadow Creek Ranch", "Pearland ISD", "low taxes",
            "home office", "vaulted ceilings", "288 corridor", "cabana",
        ],
        "mls_number": "HAR-2024-006",
    },
    {
        "title": "Galleria Luxury High-Rise — 30th Floor",
        "address": "1600 Post Oak Blvd #3012",
        "city": "Houston",
        "state": "TX",
        "zip": "77056",
        "property_type": "condo",
        "bedrooms": 2,
        "bathrooms": 2.5,
        "sqft": 1920,
        "price": 875_000,
        "status": "active",
        "description": (
            "Full-floor corner unit on the 30th floor of a Galleria luxury tower. "
            "Floor-to-ceiling windows with panoramic Uptown skyline views, Italian marble "
            "throughout, Miele kitchen appliances, and a wraparound balcony. Building "
            "amenities include 24-hr concierge, valet, infinity pool, wine cellar, and "
            "private screening room. Two dedicated parking spaces."
        ),
        "features": [
            "30th floor", "panoramic skyline views", "Italian marble", "Miele appliances",
            "wraparound balcony", "24hr concierge", "valet", "wine cellar", "infinity pool",
        ],
        "mls_number": "HAR-2024-007",
    },
    {
        "title": "The Woodlands Executive Estate",
        "address": "18 Player Point Dr",
        "city": "The Woodlands",
        "state": "TX",
        "zip": "77380",
        "property_type": "house",
        "bedrooms": 6,
        "bathrooms": 5.5,
        "sqft": 6800,
        "price": 2_150_000,
        "status": "active",
        "description": (
            "Trophy estate on a golf course lot in the prestigious Player Point enclave. "
            "Grand foyer with dual staircases, chef's kitchen with La Cornue range, wine "
            "room, home theater, gym, and a full guest suite with private entrance. "
            "Resort backyard with pool/spa, outdoor kitchen, and putting green. "
            "The Woodlands is consistently ranked one of the best places to live in America."
        ),
        "features": [
            "golf course lot", "home theater", "gym", "wine room", "putting green",
            "guest suite", "outdoor kitchen", "La Cornue range", "dual staircases",
        ],
        "mls_number": "HAR-2024-008",
    },
    {
        "title": "Montrose Victorian — Historic District",
        "address": "808 Lovett Blvd",
        "city": "Houston",
        "state": "TX",
        "zip": "77006",
        "property_type": "house",
        "bedrooms": 4,
        "bathrooms": 3.0,
        "sqft": 2400,
        "price": 849_000,
        "status": "pending",
        "description": (
            "Rare 1910 Victorian in the Avondale historic district of Montrose. Wrap-around "
            "porch, original longleaf pine floors, 10-ft ceilings, period millwork, and "
            "a completely modernized kitchen and primary bath. Detached 2-car garage with "
            "ADU potential. One block from Menil Collection, surrounded by the best "
            "dining and arts scene in Houston."
        ),
        "features": [
            "1910 Victorian", "wrap-around porch", "longleaf pine floors",
            "ADU potential", "Menil Collection nearby", "historic district",
            "modernized kitchen", "10-ft ceilings",
        ],
        "mls_number": "HAR-2024-009",
    },
    {
        "title": "Cypress Master-Planned Community Home",
        "address": "14720 Barker Landing Rd",
        "city": "Cypress",
        "state": "TX",
        "zip": "77429",
        "property_type": "house",
        "bedrooms": 5,
        "bathrooms": 4.0,
        "sqft": 3750,
        "price": 579_000,
        "status": "active",
        "description": (
            "Spacious 5-bedroom in the sought-after Bridgeland community. Open floor plan "
            "with soaring ceilings, secondary bedroom with ensuite on the first floor, "
            "large game room and media room upstairs. Three-car tandem garage. Resort-style "
            "community amenities: lazy river, splash pad, 900-acre lake, hiking, and "
            "Cy-Fair ISD schools."
        ),
        "features": [
            "Bridgeland community", "lazy river", "900-acre lake", "Cy-Fair ISD",
            "media room", "game room", "3-car tandem garage", "first-floor guest suite",
        ],
        "mls_number": "HAR-2024-010",
    },
]

# ── Houston FAQ ───────────────────────────────────────────────────────────────

DEMO_FAQ = """
FREQUENTLY ASKED QUESTIONS — Pinnacle Property Management (Houston, TX)

Q: What areas of Houston do you serve?
A: We specialize in the greater Houston metro, including Midtown, Montrose, The Heights,
   EaDo (East Downtown), Galleria/Uptown, Medical Center, Sugar Land, Katy, Pearland,
   The Woodlands, and Cypress. If you have a neighborhood in mind, just ask!

Q: Do you work with buyers, sellers, and investors?
A: Yes. We represent buyers and sellers in residential transactions, and we actively work
   with investors looking for single-family rentals, multi-family, and development lots.
   Houston has no state income tax and strong rental demand — great for investors.

Q: Texas has no state income tax — does that affect affordability significantly?
A: Absolutely. Texas has no state income tax, which helps offset higher property taxes
   (typically 2.0–2.5% in the Houston metro). Most buyers find the total cost of ownership
   very competitive versus coastal markets.

Q: How is the Houston real estate market right now?
A: Houston remains one of the strongest value markets in the country. The energy sector,
   Texas Medical Center, Port of Houston, and major corporate relocations keep demand
   steady. Inventory varies by neighborhood — call us for a current market snapshot.

Q: What school districts are considered the best near Houston?
A: Top-rated districts include Katy ISD, Fort Bend ISD (Sugar Land), Cy-Fair ISD
   (Cypress), Conroe ISD (The Woodlands), and several Houston ISD campuses. We can
   target your search by district if schools are a priority.

Q: How quickly can I schedule a showing?
A: For most active listings we can arrange a showing within 24–48 hours. Hot properties
   and new construction model homes may require 2–3 days notice.

Q: Do you offer virtual tours or video walkthroughs?
A: Yes — every active listing includes HD video. We can also do live FaceTime or Zoom
   walkthroughs with an agent for out-of-town buyers.

Q: What is the typical closing timeline in Texas?
A: Standard Texas closings run 30–45 days. Cash purchases can close in 10–14 days.
   We work with preferred lenders who can sometimes close in 21 days for financed buyers.

Q: Are there flood zones I should be aware of?
A: Flood zone awareness is critical in Houston. We always pull FEMA flood maps and
   disclose flood history on every property. Many homes outside the 100-year flood
   plain have never flooded. Ask us about specific addresses.

Q: Do you have off-market listings?
A: Yes. We maintain an exclusive inventory of off-market and coming-soon properties
   for qualified buyers. Share your criteria and we'll notify you when a match appears.

Q: What are your commission rates?
A: We follow standard Texas real estate commission structures. Sellers typically pay
   5–6% split between listing and buyer's agents. Buyer representation is usually
   at no direct cost to the buyer. Contact us for specifics on your situation.
"""

# ── Leads ─────────────────────────────────────────────────────────────────────

DEMO_LEADS = [
    {
        "name": "Maria Gonzalez",
        "phone": "+17139550201",
        "email": "maria.gonzalez@email.com",
        "source": "voice",
        "status": "qualified",
        "score": 72,
        "score_breakdown": {
            "shared_phone": 15, "shared_email": 10,
            "requested_showing": 30, "specific_neighborhood": 10,
            "spanish_speaker": 7,
        },
        "language": "es",
        "notes": (
            "Inbound call in Spanish. Looking for 3BR family home in Katy or Sugar Land, "
            "budget $500K–$650K. Moving in 60 days, husband is relocating for work at "
            "ExxonMobil. Needs good schools. Ready to tour this weekend."
        ),
    },
    {
        "name": "James Chen",
        "phone": "+17139550202",
        "email": "james.chen@techcorp.io",
        "source": "chat",
        "status": "new",
        "score": 28,
        "score_breakdown": {
            "shared_email": 10, "first_time_buyer": 8,
            "long_term_timeline": -5, "just_browsing": -10, "website_chat": 25,
        },
        "language": "en",
        "notes": (
            "Chat inquiry about EaDo lofts. First-time buyer, pre-approval in progress. "
            "Flexible timeline (3–6 months). Works in tech, wants walkable neighborhood."
        ),
    },
    {
        "name": "Ashley Williams",
        "phone": "+17139550203",
        "email": "awilliams@gmail.com",
        "source": "chat",
        "status": "appointment",
        "score": 88,
        "score_breakdown": {
            "shared_phone": 15, "shared_email": 10,
            "requested_showing": 30, "pre_approved": 20,
            "specific_property": 13,
        },
        "language": "en",
        "notes": (
            "Highly motivated buyer. Pre-approved at $600K. Wants to see the Katy "
            "new construction (HAR-2024-004) and the Pearland executive home. "
            "Appointment confirmed for Saturday morning."
        ),
    },
    {
        "name": "David Okafor",
        "phone": "+17139550204",
        "source": "voice",
        "status": "contacted",
        "score": 42,
        "score_breakdown": {
            "shared_phone": 15, "requested_callback": 15,
            "vague_timeline": -5, "no_email": -5, "specific_area": 22,
        },
        "language": "en",
        "notes": (
            "Inbound voice inquiry about The Woodlands estate listings. Investor/end-user. "
            "Wants callback — didn't leave email. Interested in $2M+ range."
        ),
    },
    {
        "name": "Sarah Martinez",
        "phone": "+17139550205",
        "email": "smartinez@outlook.com",
        "source": "web_form",
        "status": "qualified",
        "score": 65,
        "score_breakdown": {
            "shared_phone": 15, "shared_email": 10,
            "specific_neighborhood": 10, "concrete_budget": 20, "web_form": 10,
        },
        "language": "en",
        "notes": (
            "Web form submission. Interested in Montrose Victorian or similar Heights/Montrose "
            "area homes. Budget $750K–$950K. Cash buyer, no financing contingency. "
            "Moving from Austin — remote worker."
        ),
    },
    {
        "name": "Robert Kim",
        "phone": "+17139550206",
        "email": "rkim@gmail.com",
        "source": "chat",
        "status": "new",
        "score": 18,
        "score_breakdown": {
            "shared_email": 10, "early_stage": -5,
            "no_timeline": -5, "just_browsing": -10, "website_chat": 28,
        },
        "language": "en",
        "notes": (
            "Chat about Galleria high-rises. Relocating to Houston for work in 6+ months. "
            "Early stage — collecting information. No pre-approval yet."
        ),
    },
    {
        "name": "Fatima Al-Hassan",
        "phone": "+17139550207",
        "email": "fatima.alhassan@email.com",
        "source": "voice",
        "status": "qualified",
        "score": 80,
        "score_breakdown": {
            "shared_phone": 15, "shared_email": 10,
            "requested_showing": 30, "pre_approved": 20,
            "concrete_budget": 5,
        },
        "language": "en",
        "notes": (
            "Inbound call. Medical professional at Texas Medical Center. Looking for "
            "Pearland or Sugar Land with 4BR, pool preferred. Budget up to $600K, "
            "pre-approved. Wants weekend showing. Very motivated."
        ),
    },
    {
        "name": "Michael Torres",
        "phone": "+17139550208",
        "source": "web_form",
        "status": "new",
        "score": 12,
        "score_breakdown": {
            "shared_phone": 15, "no_email": -5,
            "vague_request": -8, "web_form": 10,
        },
        "language": "en",
        "notes": (
            "Web form inquiry — general interest in Houston investment properties. "
            "No budget or timeline specified. Follow-up call needed."
        ),
    },
]

# ── Conversation transcripts ──────────────────────────────────────────────────

def _ts(offset_minutes: int = 0) -> str:
    base = datetime(2026, 5, 20, 14, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=offset_minutes)).isoformat()


MARIA_TRANSCRIPT = [
    {"role": "user",      "content": "Hola, buenos días. Estoy interesada en casas en Katy o Sugar Land.", "timestamp": _ts(0)},
    {"role": "assistant", "content": "¡Buenos días! Claro, con mucho gusto le ayudo. ¿Cuántas recámaras necesita y cuál es su presupuesto aproximado?", "timestamp": _ts(0)},
    {"role": "user",      "content": "Tres o cuatro recámaras, presupuesto entre 500 y 650 mil dólares. Mi esposo va a trabajar en ExxonMobil.", "timestamp": _ts(1)},
    {"role": "assistant", "content": "Perfecto. Tenemos varias opciones excelentes en ese rango. En Katy tenemos una casa nueva en Cinco Ranch con 5 recámaras a $649,000 — escuelas de Katy ISD, que son de las mejores en Texas. En Sugar Land hay una en First Colony con 4 recámaras a $565,000, en el distrito Fort Bend ISD. ¿Le gustaría programar una visita para ver alguna de ellas?", "timestamp": _ts(1)},
    {"role": "user",      "content": "Sí, me gustaría ver ambas si es posible. ¿Pueden ser este fin de semana?", "timestamp": _ts(2)},
    {"role": "assistant", "content": "¡Claro que sí! Puedo programarle visitas para el sábado por la mañana. ¿Me puede dar su nombre completo y número de teléfono para confirmarle?", "timestamp": _ts(2)},
    {"role": "user",      "content": "Soy María Gonzalez, mi número es 713-955-0201.", "timestamp": _ts(3)},
    {"role": "assistant", "content": "Perfecto, María. La agendaré para el sábado. Le enviaremos la confirmación por mensaje de texto. ¿Tiene alguna pregunta más por ahora?", "timestamp": _ts(3)},
    {"role": "user",      "content": "No, muchas gracias. Hasta el sábado.", "timestamp": _ts(4)},
    {"role": "assistant", "content": "Con mucho gusto, María. ¡Hasta el sábado! Que tenga un excelente día.", "timestamp": _ts(4)},
]

JAMES_TRANSCRIPT = [
    {"role": "user",      "content": "Hey, I'm looking at the EaDo loft listing — the one on Commerce St. Is that still available?", "timestamp": _ts(0)},
    {"role": "assistant", "content": "Hi! Yes, the EaDo loft at 2401 Commerce St #310 is still active and available for showings. It's a 1-bed / 1-bath, 1,050 sq ft with 16-ft ceilings and exposed brick — a really unique space. Are you looking to buy or rent?", "timestamp": _ts(0)},
    {"role": "user",      "content": "Buy. First time buyer. I'm in tech, want something walkable. What's the HOA like?", "timestamp": _ts(1)},
    {"role": "assistant", "content": "Good choice for the area! The HOA covers building amenities — rooftop dog run, co-working lounge, and secured parking. The monthly HOA is around $350/month which includes water and trash. The building is very popular with tech folks who want a short commute and walkable nightlife. Would you like to schedule a tour?", "timestamp": _ts(1)},
    {"role": "user",      "content": "Maybe in a few weeks — I'm still waiting on my pre-approval. Can you send me more details?", "timestamp": _ts(2)},
    {"role": "assistant", "content": "Absolutely! If you share your email I'll send over the full listing package with floor plan and building amenities. And when your pre-approval comes through, just reach out — we can usually get you in within 24–48 hours.", "timestamp": _ts(2)},
    {"role": "user",      "content": "Great, it's james.chen@techcorp.io", "timestamp": _ts(3)},
    {"role": "assistant", "content": "Perfect, sending that over now. We'll be in touch, James. Good luck with the pre-approval — feel free to message anytime if you have questions!", "timestamp": _ts(3)},
]

# ── Maintenance / tenant request leads ───────────────────────────────────────

DEMO_REQUESTS = [
    {
        "name": "Carlos Mendez",
        "phone": "+17139550301",
        "source": "voice",
        "status": "contacted",
        "score": 0,
        "language": "en",
        "notes": "[MAINTENANCE] AC unit not working — unit 304, Galleria complex. Priority 2 ticket logged. Maintenance team notified.",
    },
    {
        "name": "Jennifer Park",
        "phone": "+17139550302",
        "email": "jpark@email.com",
        "source": "voice",
        "status": "appointment",
        "score": 0,
        "language": "en",
        "notes": "[LEASE RENEWAL] Unit 512, The Woodlands property. Lease expires Aug 31. Renewal call scheduled Thursday 2pm with property manager.",
    },
    {
        "name": "Kevin Johnson",
        "phone": "+17139550303",
        "source": "voice",
        "status": "contacted",
        "score": 0,
        "language": "en",
        "notes": "[MAINTENANCE] Emergency — water leak from ceiling, unit 211, Shadow Creek (Pearland). Priority 1 ticket. Technician dispatched within 2hrs.",
    },
]

def _ts2(base_hour: int, offset_minutes: int = 0) -> str:
    base = datetime(2026, 5, 21, base_hour, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=offset_minutes)).isoformat()


CARLOS_TRANSCRIPT = [
    {"role": "user",      "content": "Hi, my AC hasn't been working since yesterday. It's really hot in my unit.", "timestamp": _ts2(9, 0)},
    {"role": "assistant", "content": "I'm really sorry to hear that — I'm logging an urgent maintenance request right now. Can you confirm your full name and unit number?", "timestamp": _ts2(9, 0)},
    {"role": "user",      "content": "Carlos Mendez, unit 304 at the Galleria complex, 1600 Post Oak.", "timestamp": _ts2(9, 1)},
    {"role": "assistant", "content": "Thank you Carlos. I've created a Priority 2 maintenance ticket for HVAC at unit 304. Our team will contact you within 4 hours to schedule a technician. You'll also receive a text confirmation at this number. Is there anything else I can help with?", "timestamp": _ts2(9, 1)},
    {"role": "user",      "content": "No, that's all. Just please make it quick, it's really hot.", "timestamp": _ts2(9, 2)},
    {"role": "assistant", "content": "Absolutely, we'll prioritize this. You'll hear from the maintenance team shortly. Stay cool, Carlos!", "timestamp": _ts2(9, 2)},
]

JENNIFER_TRANSCRIPT = [
    {"role": "user",      "content": "Hi, I want to ask about renewing my lease. It expires in about 2 months.", "timestamp": _ts2(11, 0)},
    {"role": "assistant", "content": "Of course! I'd be happy to help with your lease renewal. Can I get your name and unit number?", "timestamp": _ts2(11, 0)},
    {"role": "user",      "content": "Jennifer Park, unit 512 at the Woodlands property.", "timestamp": _ts2(11, 1)},
    {"role": "assistant", "content": "Thank you Jennifer. Your lease at The Woodlands expires August 31st. Current renewal options are: 12-month term at $2,150/month, or a 6-month term at $2,280/month. Would you like to schedule a call with your property manager to go over details?", "timestamp": _ts2(11, 1)},
    {"role": "user",      "content": "Yes please, can we do sometime this week?", "timestamp": _ts2(11, 2)},
    {"role": "assistant", "content": "I've scheduled a renewal consultation for Thursday at 2pm with your property manager. You'll receive a calendar invite by text. Is there anything else?", "timestamp": _ts2(11, 2)},
    {"role": "user",      "content": "No, that's perfect. Thank you!", "timestamp": _ts2(11, 3)},
    {"role": "assistant", "content": "You're welcome Jennifer! We'll see you Thursday at 2pm.", "timestamp": _ts2(11, 3)},
]

KEVIN_TRANSCRIPT = [
    {"role": "user",      "content": "Hey, there's water dripping from my bathroom ceiling. Looks like it's coming from the unit above me.", "timestamp": _ts2(16, 0)},
    {"role": "assistant", "content": "That's an emergency — I'm flagging this as a Priority 1 maintenance request right now and alerting the on-call team. Can I get your name and unit number?", "timestamp": _ts2(16, 0)},
    {"role": "user",      "content": "Kevin Johnson, unit 211, Shadow Creek complex in Pearland.", "timestamp": _ts2(16, 1)},
    {"role": "assistant", "content": "Kevin, I've created an emergency ticket for unit 211. A technician has been dispatched and should arrive within 2 hours. Please place towels under the leak and avoid the area if the dripping is heavy. The building manager has also been notified. You'll get a text when the technician is on the way.", "timestamp": _ts2(16, 1)},
    {"role": "user",      "content": "Okay, thanks for the quick response.", "timestamp": _ts2(16, 2)},
    {"role": "assistant", "content": "Of course — that's what we're here for. Stay safe and we'll have someone out to you very soon.", "timestamp": _ts2(16, 2)},
]

# ── Seed function ─────────────────────────────────────────────────────────────

async def seed():
    sb = get_supabase_admin()
    now = datetime.now(timezone.utc)

    print("=" * 60)
    print("NexaDesk — Pinnacle Property Management demo seed")
    print("=" * 60)

    if EMBED_ENABLED:
        # Bootstrap the Qdrant client that ingest_text reads from the global
        import app.dependencies as _deps
        from qdrant_client import AsyncQdrantClient
        from app.dependencies import ensure_collection
        _deps._qdrant_client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        await ensure_collection(_deps._qdrant_client, settings)
        print("Qdrant client initialised.")
    else:
        print("NOTE: EMBED_API_KEY not set — Qdrant ingestion will be skipped.")
        print("      Set EMBED_API_KEY in .env and re-run to enable RAG search.")

    # 1. Company — update first existing or create new
    existing_companies = sb.table("companies").select("id, name").limit(1).execute()
    if existing_companies.data:
        company_id = existing_companies.data[0]["id"]
        sb.table("companies").update(DEMO_COMPANY).eq("id", company_id).execute()
        print(f"[company] Updated: {DEMO_COMPANY['name']} ({company_id})")
    else:
        result = sb.table("companies").insert(DEMO_COMPANY).execute()
        company_id = result.data[0]["id"]
        print(f"[company] Created: {DEMO_COMPANY['name']} ({company_id})")

    # 2. Properties — upsert by mls_number
    print("\n[properties]")
    property_ids: dict[str, str] = {}  # mls_number -> id
    for prop_data in DEMO_PROPERTIES:
        existing = (
            sb.table("properties")
            .select("id")
            .eq("mls_number", prop_data["mls_number"])
            .execute()
        )
        if existing.data:
            prop_id = existing.data[0]["id"]
            result = sb.table("properties").update({**prop_data, "company_id": company_id}).eq("id", prop_id).execute()
            property_ids[prop_data["mls_number"]] = prop_id
            prop_row = result.data[0] if result.data else {**prop_data, "id": prop_id, "company_id": company_id}
            print(f"  updated  {prop_data['title']}")
        else:
            row = {**prop_data, "company_id": company_id}
            result = sb.table("properties").insert(row).execute()
            prop_id = result.data[0]["id"]
            property_ids[prop_data["mls_number"]] = prop_id
            prop_row = result.data[0]
            print(f"  created  {prop_data['title']}")

        # Always ingest into Qdrant (idempotent — overwrites by doc_id)
        if EMBED_ENABLED:
            text = property_to_text(prop_row)
            await ingest_text(
                text=text,
                company_id=company_id,
                metadata={
                    "source_type": "property_form",
                    "property_id": prop_id,
                    "doc_category": "listing",
                    "filename": f"property_{prop_id[:8]}.txt",
                },
            )
            print(f"            -> ingested into Qdrant")

    # 3. FAQ — always re-ingest (ingest_text is idempotent per content hash)
    print("\n[faq] Ingesting company FAQ...")
    await ingest_text(
        text=DEMO_FAQ,
        company_id=company_id,
        metadata={
            "source_type": "text_paste",
            "doc_category": "faq",
            "filename": "pinnacle_faq.txt",
        },
    )
    print("  done")

    # 4. Leads — insert only if phone not already present for this company
    print("\n[leads]")
    lead_ids: dict[str, str] = {}  # name -> id
    for lead_data in DEMO_LEADS:
        phone = lead_data.get("phone", "")
        existing = (
            sb.table("leads")
            .select("id")
            .eq("company_id", company_id)
            .eq("phone", phone)
            .execute()
        )
        if existing.data:
            lead_id = existing.data[0]["id"]
            lead_ids[lead_data["name"]] = lead_id
            print(f"  skip (exists)  {lead_data['name']}")
        else:
            row = {**lead_data, "company_id": company_id}
            result = sb.table("leads").insert(row).execute()
            lead_id = result.data[0]["id"]
            lead_ids[lead_data["name"]] = lead_id
            print(f"  created        {lead_data['name']} (score={lead_data.get('score', 0)})")

    # 5. Conversations — 2 demo transcripts
    print("\n[conversations]")
    conv_specs = [
        {
            "session_id": "demo-voice-maria-20260520",
            "lead_name": "Maria Gonzalez",
            "channel": "voice",
            "language": "es",
            "transcript": MARIA_TRANSCRIPT,
            "summary": "Spanish-language inbound call. Buyer relocating to Houston for spouse's ExxonMobil role. Wants 3–4BR in Katy or Sugar Land, budget $500K–$650K. Requested Saturday showing for Cinco Ranch and First Colony listings.",
            "sentiment": "positive",
            "call_duration": 312,
            "started_at": datetime(2026, 5, 20, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "ended_at":   datetime(2026, 5, 20, 14, 5, 12, tzinfo=timezone.utc).isoformat(),
        },
        {
            "session_id": "demo-chat-james-20260520",
            "lead_name": "James Chen",
            "channel": "chat",
            "language": "en",
            "transcript": JAMES_TRANSCRIPT,
            "summary": "Chat inquiry about EaDo loft on Commerce St. First-time buyer in tech. Waiting on pre-approval, interested in a showing in a few weeks. Captured email for follow-up.",
            "sentiment": "positive",
            "call_duration": None,
            "started_at": datetime(2026, 5, 20, 15, 30, 0, tzinfo=timezone.utc).isoformat(),
            "ended_at":   datetime(2026, 5, 20, 15, 38, 0, tzinfo=timezone.utc).isoformat(),
        },
    ]
    for spec in conv_specs:
        existing = (
            sb.table("conversations")
            .select("id")
            .eq("session_id", spec["session_id"])
            .execute()
        )
        if existing.data:
            print(f"  skip (exists)  {spec['session_id']}")
            continue
        lead_id = lead_ids.get(spec["lead_name"])
        row = {
            "company_id":       company_id,
            "lead_id":          lead_id,
            "channel":          spec["channel"],
            "session_id":       spec["session_id"],
            "transcript":       spec["transcript"],
            "summary":          spec["summary"],
            "sentiment":        spec["sentiment"],
            "language":         spec["language"],
            "call_duration":    spec["call_duration"],
            "started_at":       spec["started_at"],
            "ended_at":         spec["ended_at"],
        }
        sb.table("conversations").insert(row).execute()
        print(f"  created  {spec['channel']:5s}  {spec['lead_name']}")

    # 6. Appointments — 3 upcoming showings relative to now
    print("\n[appointments]")
    apt_specs = [
        {
            "lead_name":    "Maria Gonzalez",
            "mls_numbers":  ["HAR-2024-004"],  # Katy new construction
            "datetime":     (now + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0),
            "type":         "showing",
            "status":       "scheduled",
            "duration_minutes": 60,
            "notes":        "Saturday morning tour — Cinco Ranch new construction. Bring Fort Bend ISD school comparison sheet.",
        },
        {
            "lead_name":    "Ashley Williams",
            "mls_numbers":  ["HAR-2024-004", "HAR-2024-006"],  # Katy + Pearland
            "datetime":     (now + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0),
            "type":         "showing",
            "status":       "confirmed",
            "duration_minutes": 90,
            "notes":        "Back-to-back showings: Katy new construction then Pearland executive home. Pre-approved at $600K.",
        },
        {
            "lead_name":    "Sarah Martinez",
            "mls_numbers":  ["HAR-2024-009"],  # Montrose Victorian
            "datetime":     (now + timedelta(days=5)).replace(hour=14, minute=0, second=0, microsecond=0),
            "type":         "showing",
            "status":       "scheduled",
            "duration_minutes": 45,
            "notes":        "Cash buyer from Austin. Primary interest is Montrose Victorian. Discuss historic district deed restrictions.",
        },
    ]
    for spec in apt_specs:
        lead_id = lead_ids.get(spec["lead_name"])
        if not lead_id:
            print(f"  skip (lead not found)  {spec['lead_name']}")
            continue

        # Use the first property in the list as the linked property
        prop_id = property_ids.get(spec["mls_numbers"][0]) if spec["mls_numbers"] else None

        # Idempotency: skip if same lead + datetime already exists
        dt_str = spec["datetime"].isoformat()
        existing = (
            sb.table("appointments")
            .select("id")
            .eq("company_id", company_id)
            .eq("lead_id", lead_id)
            .eq("datetime", dt_str)
            .execute()
        )
        if existing.data:
            print(f"  skip (exists)  {spec['lead_name']}")
            continue

        row = {
            "company_id":       company_id,
            "lead_id":          lead_id,
            "property_id":      prop_id,
            "datetime":         dt_str,
            "duration_minutes": spec["duration_minutes"],
            "type":             spec["type"],
            "status":           spec["status"],
            "notes":            spec["notes"],
        }
        sb.table("appointments").insert(row).execute()
        print(f"  created  {spec['type']:8s}  {spec['lead_name']}  @ {spec['datetime'].strftime('%a %b %d %H:%M')}")

    # 7. Tenant / maintenance request leads + conversations
    print("\n[tenant requests]")
    request_convs = [
        {
            "lead": DEMO_REQUESTS[0],
            "session_id": "demo-maint-carlos-20260521",
            "transcript": CARLOS_TRANSCRIPT,
            "summary": "Tenant maintenance call — AC not working at unit 304 (Galleria). Priority 2 ticket created. Team notified.",
            "sentiment": "neutral",
            "started_at": _ts2(9, 0),
            "ended_at":   _ts2(9, 3),
            "call_duration": 180,
        },
        {
            "lead": DEMO_REQUESTS[1],
            "session_id": "demo-lease-jennifer-20260521",
            "transcript": JENNIFER_TRANSCRIPT,
            "summary": "Tenant lease renewal inquiry — unit 512 (Woodlands). Renewal options quoted. Consultation scheduled Thursday 2pm.",
            "sentiment": "positive",
            "started_at": _ts2(11, 0),
            "ended_at":   _ts2(11, 4),
            "call_duration": 240,
        },
        {
            "lead": DEMO_REQUESTS[2],
            "session_id": "demo-maint-kevin-20260521",
            "transcript": KEVIN_TRANSCRIPT,
            "summary": "Emergency maintenance — water leak from ceiling at unit 211 (Shadow Creek, Pearland). Priority 1, technician dispatched.",
            "sentiment": "neutral",
            "started_at": _ts2(16, 0),
            "ended_at":   _ts2(16, 3),
            "call_duration": 150,
        },
    ]
    for spec in request_convs:
        lead_data = spec["lead"]
        phone = lead_data.get("phone", "")
        existing_lead = (
            sb.table("leads").select("id").eq("company_id", company_id).eq("phone", phone).execute()
        )
        if existing_lead.data:
            lead_id = existing_lead.data[0]["id"]
            print(f"  skip lead (exists)  {lead_data['name']}")
        else:
            row = {**lead_data, "company_id": company_id}
            result = sb.table("leads").insert(row).execute()
            lead_id = result.data[0]["id"]
            print(f"  created lead  {lead_data['name']}")

        existing_conv = (
            sb.table("conversations").select("id").eq("session_id", spec["session_id"]).execute()
        )
        if existing_conv.data:
            print(f"  skip conv  (exists)  {spec['session_id']}")
        else:
            sb.table("conversations").insert({
                "company_id":    company_id,
                "lead_id":       lead_id,
                "channel":       "voice",
                "session_id":    spec["session_id"],
                "transcript":    spec["transcript"],
                "summary":       spec["summary"],
                "sentiment":     spec["sentiment"],
                "language":      "en",
                "call_duration": spec["call_duration"],
                "started_at":    spec["started_at"],
                "ended_at":      spec["ended_at"],
            }).execute()
            print(f"  created conv  {lead_data['name']}")

    # ── Summary ──────────────────────────────────────────────────────────────
    leads_count    = sb.table("leads").select("id", count="exact").eq("company_id", company_id).execute()
    props_count    = sb.table("properties").select("id", count="exact").eq("company_id", company_id).execute()
    convs_count    = sb.table("conversations").select("id", count="exact").eq("company_id", company_id).execute()
    apts_count     = sb.table("appointments").select("id", count="exact").eq("company_id", company_id).execute()

    print("\n" + "=" * 60)
    print("Seed complete — Pinnacle Property Management")
    print(f"  Company ID   : {company_id}")
    print(f"  Properties   : {props_count.count}")
    print(f"  Leads        : {leads_count.count}")
    print(f"  Conversations: {convs_count.count}")
    print(f"  Appointments : {apts_count.count}")
    print("=" * 60)
    print("Log into the dashboard to see your demo data.")


if __name__ == "__main__":
    asyncio.run(seed())

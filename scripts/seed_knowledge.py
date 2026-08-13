"""
Knowledge base seeder for Pinnacle Property Management demo.

Adds UAE, UK, and US properties + market-rate knowledge documents.
Run inside the Docker container:

  # Production (seed Qdrant + Supabase):
  docker exec nexadesk_prod-app-1 python scripts/seed_knowledge.py

  # Dev (skip Supabase inserts — already done by prod run):
  docker exec nexa_desk-app-1 python scripts/seed_knowledge.py --qdrant-only

  # Re-seed just Qdrant from existing Supabase properties:
  docker exec nexadesk_prod-app-1 python scripts/seed_knowledge.py --reingest-existing
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

COMPANY_ID = "ae14c9eb-e18c-4ec3-bce8-cd4a57db3bb4"  # Pinnacle Property Management


# ── New properties to add ─────────────────────────────────────────────────────

NEW_PROPERTIES = [
    # ── UAE — Dubai ────────────────────────────────────────────────────────
    {
        "title": "Dubai Marina — The Pearl Residences | 2BR",
        "address": "The Pearl, Dubai Marina, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 1350,
        "price": 1950000,
        "status": "active",
        "description": (
            "Iconic 33rd-floor waterfront apartment in Dubai Marina with panoramic views of the Arabian Gulf "
            "and marina skyline. Fully fitted European kitchen, master bedroom with en-suite, floor-to-ceiling "
            "glass throughout. Building amenities include rooftop infinity pool, gym, concierge, and valet parking. "
            "5 min walk to Dubai Marina Mall and JBR beach. Service charge AED 14/sqft/yr. RERA registration "
            "number DXB-RE-2024-0841."
        ),
        "features": [
            "Sea and marina views", "Floor-to-ceiling glass",
            "Rooftop infinity pool", "Covered parking", "24/7 concierge",
            "Close to JBR beach", "Low floor plan available on request",
        ],
    },
    {
        "title": "Downtown Dubai — Burj Vista | 1BR Facing Burj Khalifa",
        "address": "Burj Vista Tower 1, Downtown Dubai, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "apartment",
        "bedrooms": 1, "bathrooms": 1, "sqft": 875,
        "price": 1850000,
        "status": "active",
        "description": (
            "Premium 1-bedroom in the sought-after Burj Vista tower with a direct Burj Khalifa and "
            "Dubai Fountain view from the living room. Semi-furnished with high-spec finishes. "
            "150m from Dubai Mall, walking distance to Emaar Boulevard restaurants. "
            "Annual rent for similar units: AED 105,000–130,000 (gross yield ~6%). "
            "Ideal for end-users or buy-to-let investors."
        ),
        "features": [
            "Direct Burj Khalifa view", "Burj Khalifa & Fountain view",
            "Steps from Dubai Mall", "Emaar-managed building",
            "Pool & gym", "High rental yield area",
        ],
    },
    {
        "title": "Palm Jumeirah — Signature Villa | 5BR Beachfront",
        "address": "Frond N, Palm Jumeirah, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "house",
        "bedrooms": 5, "bathrooms": 6, "sqft": 7200,
        "price": 23500000,
        "status": "active",
        "description": (
            "One-of-a-kind 5-bedroom signature villa on Palm Jumeirah frond N, featuring a private beach, "
            "50-ft swimming pool, and direct access to the Arabian Gulf. Built-up area 7,200 sqft across "
            "3 floors. Custom interiors with Italian marble, Gaggenau appliances, and smart-home automation. "
            "External terrace area an additional 2,800 sqft. 12-min drive to Atlantis, 15 min to JBR. "
            "Similar Palm villas renting at AED 900,000–1,400,000/yr."
        ),
        "features": [
            "Private beach access", "50-ft private pool",
            "Smart home automation", "Italian marble throughout",
            "Panoramic sea views", "3 covered parking spaces",
            "Maid's room and driver's quarters",
        ],
    },
    {
        "title": "Business Bay — Executive Bay | Studio Investment",
        "address": "Executive Bay Tower B, Business Bay, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "apartment",
        "bedrooms": 0, "bathrooms": 1, "sqft": 580,
        "price": 780000,
        "status": "active",
        "description": (
            "High-yield studio in the heart of Business Bay, ideal for investors. "
            "Currently tenanted at AED 58,000/yr (gross yield 7.4%). "
            "Canal views from upper floors. Fully fitted kitchen, built-in wardrobes. "
            "1 min walk to Business Bay Metro, 5 min to DIFC and Downtown. "
            "Area median studio price AED 680,000–960,000. "
            "Strong capital appreciation: +18% in 3 years."
        ),
        "features": [
            "High rental yield 7%+", "Tenanted — immediate income",
            "Business Bay Metro access", "Canal views available",
            "Close to DIFC", "Capital appreciation area",
        ],
    },
    {
        "title": "Jumeirah Village Circle — The Terraces | 2BR Family",
        "address": "The Terraces, JVC District 11, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 1180,
        "price": 980000,
        "status": "active",
        "description": (
            "Spacious 2-bedroom apartment in Jumeirah Village Circle — one of Dubai's most affordable "
            "communities with excellent rental yields (8–10%). Large terrace overlooking green landscapes. "
            "Open-plan living, separate laundry room, 2 parking spaces. "
            "Similar units rent at AED 75,000–90,000/yr. "
            "Close to Circle Mall, JSS International School, and Al Khail Road. "
            "Perfect for families or buy-to-let investors targeting long-term tenants."
        ),
        "features": [
            "Large terrace", "2 parking spaces",
            "High rental yield 8–10%", "Family-friendly community",
            "Close to Circle Mall", "Pet-friendly building",
        ],
    },
    {
        "title": "Dubai Hills Estate — Maple Townhouse | 4BR",
        "address": "Maple Phase 3, Dubai Hills Estate, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "house",
        "bedrooms": 4, "bathrooms": 4, "sqft": 2900,
        "price": 5400000,
        "status": "active",
        "description": (
            "4-bedroom Maple townhouse in the prestigious Dubai Hills Estate by Emaar. "
            "Corner plot with extended garden, private garage for 2 cars. "
            "Upgraded kitchen and bathrooms with premium fixtures. "
            "Walking distance to Dubai Hills Mall (500m), Dubai Hills Park, and the 18-hole championship golf course. "
            "Community amenities: school, hospital, jogging tracks, and cycling paths. "
            "Premium townhouses in this phase rent at AED 280,000–340,000/yr."
        ),
        "features": [
            "Corner plot with large garden", "2-car garage",
            "500m to Dubai Hills Mall", "Golf course community",
            "Gated community", "Upgraded finishes",
            "Near Dubai Hills Hospital", "Schools within walking distance",
        ],
    },
    {
        "title": "Creek Harbour — Creekside 18 | 1BR Creek View",
        "address": "Creekside 18 Tower A, Dubai Creek Harbour, Dubai",
        "city": "Dubai", "state": "Dubai", "zip": "",
        "property_type": "apartment",
        "bedrooms": 1, "bathrooms": 1, "sqft": 790,
        "price": 1550000,
        "status": "active",
        "description": (
            "Modern 1-bedroom in Emaar's Dubai Creek Harbour development — Dubai's fastest-growing "
            "waterfront district. Views of the Dubai Creek Tower (set to be the world's tallest structure). "
            "Handover Q4 2024 — ready now. Fitted kitchen, balcony with creek views. "
            "The Cove retail plaza and promenade 3 min walk. "
            "Off-plan launches in same area now priced 30% above this unit. "
            "Expected rental: AED 85,000–100,000/yr."
        ),
        "features": [
            "Creek Tower views", "Waterfront promenade access",
            "Emaar developer quality", "Ready to occupy",
            "High growth corridor", "Metro connectivity planned 2026",
        ],
    },
    {
        "title": "Abu Dhabi — Saadiyat Island | 2BR Cultural District",
        "address": "Mamsha Al Saadiyat, Saadiyat Island, Abu Dhabi",
        "city": "Abu Dhabi", "state": "Abu Dhabi", "zip": "",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 1680,
        "price": 3900000,
        "status": "active",
        "description": (
            "Beachfront 2-bedroom apartment in Mamsha Al Saadiyat — the only residential beachfront "
            "in Abu Dhabi's Cultural District, walking distance to the Louvre Abu Dhabi and Guggenheim "
            "(under construction). White sandy beach access from residence. "
            "Premium finishes, wraparound balcony with sea views. "
            "Saadiyat 1BR comparable units sell at AED 1.8M–2.4M; 2BR AED 3.0M–4.5M. "
            "Annual service charge: AED 18/sqft."
        ),
        "features": [
            "Private beach access", "Louvre Abu Dhabi walking distance",
            "Sea views", "Cultural District location",
            "Guggenheim Abu Dhabi nearby", "Premium island community",
        ],
    },
    # ── UK — London ────────────────────────────────────────────────────────
    {
        "title": "London Canary Wharf — Pan Peninsula | 2BR",
        "address": "Pan Peninsula, 3 Millharbour, Canary Wharf, London E14",
        "city": "London", "state": "England", "zip": "E14 9XP",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 1050,
        "price": 895000,
        "status": "active",
        "description": (
            "Stunning 2-bedroom apartment in the iconic Pan Peninsula tower with panoramic City and Thames views. "
            "East Tower, 36th floor. Open-plan living, floor-to-ceiling glazing, Miele kitchen appliances. "
            "24/7 concierge, spa, gym, cinema, and residents' pool in the building. "
            "1 min walk to South Quay DLR, 5 min to Canary Wharf Jubilee Line. "
            "Leasehold: 999 years. Service charge £5,200/yr. Ground rent peppercorn. "
            "Similar units let at £3,800–£4,500/month."
        ),
        "features": [
            "36th floor Thames and City views", "Building spa and pool",
            "24/7 concierge", "1 min to DLR",
            "999-year leasehold", "Secure underground parking available",
        ],
    },
    {
        "title": "London Battersea — Nine Elms | 1BR Riverside",
        "address": "Embassy Gardens, Nine Elms, London SW8",
        "city": "London", "state": "England", "zip": "SW8 5DA",
        "property_type": "apartment",
        "bedrooms": 1, "bathrooms": 1, "sqft": 720,
        "price": 540000,
        "status": "active",
        "description": (
            "Stylish 1-bedroom in the Embassy Gardens development beside the US Embassy — one of London's "
            "most talked-about regeneration zones. Access to the Sky Pool (glass-bottomed pool between two towers, "
            "35ft above ground). Balcony with Thames-adjacent views. "
            "Northern Line extension (Nine Elms station) opened 2021 — Zone 1/2, 20 min to Oxford Circus. "
            "Service charge £3,100/yr. Leasehold 250 years. "
            "Typical let: £2,100–£2,600/month."
        ),
        "features": [
            "Sky Pool access", "Near US Embassy",
            "Nine Elms Tube station", "Zone 1/2",
            "New regeneration zone", "Balcony",
        ],
    },
    {
        "title": "Manchester Northern Quarter — 2BR City Apartment",
        "address": "NOMA, Angel Meadow, Manchester M4",
        "city": "Manchester", "state": "England", "zip": "M4 7BH",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 950,
        "price": 295000,
        "status": "active",
        "description": (
            "Contemporary 2-bedroom apartment in Manchester's NOMA tech district — one of the UK's fastest "
            "growing BTL hotspots. Open-plan design with Juliet balconies, underfloor heating, built-in storage. "
            "10 min walk to Piccadilly Gardens and Manchester Victoria. "
            "Average Manchester city-centre 2BR asking rent: £1,400–£1,800/month (yield 6–7%). "
            "Service charge £1,800/yr. Leasehold 250 years. "
            "Strong demand from Manchester's 100,000+ student and young-professional population."
        ),
        "features": [
            "NOMA tech district", "High BTL yield 6–7%",
            "Underfloor heating", "10 min to Piccadilly",
            "Strong rental demand", "Leasehold 250 years",
        ],
    },
    {
        "title": "Edinburgh New Town — Georgian Apartment | 3BR",
        "address": "Heriot Row, New Town, Edinburgh EH3",
        "city": "Edinburgh", "state": "Scotland", "zip": "EH3 6HS",
        "property_type": "apartment",
        "bedrooms": 3, "bathrooms": 2, "sqft": 1820,
        "price": 625000,
        "status": "active",
        "description": (
            "A* listed Georgian mid-floor apartment on one of Edinburgh New Town's finest streets. "
            "3 double bedrooms, 14-ft ceilings, original cornicing and plasterwork, wood-burning fireplace. "
            "Recently refurbished throughout with underfloor heating, Siemens kitchen. "
            "Private residents' garden. Freehold (Scottish law: outright ownership). "
            "Short-term let licence approved — Airbnb revenue £48,000–£65,000/yr. "
            "Long-term rent equivalent: £2,600–£3,000/month."
        ),
        "features": [
            "A* listed Georgian building", "14-ft ceilings with cornicing",
            "Private residents' garden", "STL licence approved",
            "Freehold (Scots law)", "Original period features",
        ],
    },
    {
        "title": "Bristol Clifton — Victorian Townhouse | 4BR",
        "address": "Canynge Road, Clifton, Bristol BS8",
        "city": "Bristol", "state": "England", "zip": "BS8 3LH",
        "property_type": "house",
        "bedrooms": 4, "bathrooms": 3, "sqft": 2400,
        "price": 895000,
        "status": "active",
        "description": (
            "Beautiful 4-bedroom Victorian townhouse in Clifton Village — Bristol's most desirable postcode. "
            "Fully refurbished with modern kitchen/diner extension and 3 bathrooms. "
            "Private walled south-facing garden, original sash windows, ornate fireplaces. "
            "100m from Clifton Village boutiques, 400m from Suspension Bridge. "
            "Freehold. Council tax Band G (Bristol). "
            "5 min walk to Clifton Down Station (Zone A, 15 min to Temple Meads). "
            "Comparable houses on the road sold: £850K–£990K in 2024."
        ),
        "features": [
            "Walled south-facing garden", "Modern extension",
            "Clifton Village location", "Freehold",
            "Victorian period features", "Near Suspension Bridge",
        ],
    },
    # ── US — Additional cities ─────────────────────────────────────────────
    {
        "title": "Miami Brickell — Icon Brickell | 2BR Bay View",
        "address": "Icon Brickell Tower 2, 475 Brickell Ave, Miami FL 33131",
        "city": "Miami", "state": "FL", "zip": "33131",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 1280,
        "price": 725000,
        "status": "active",
        "description": (
            "Luxury 2/2 in the iconic Icon Brickell tower with breathtaking Biscayne Bay views. "
            "Italian marble floors, Sub-Zero/Wolf appliances, wraparound balcony. "
            "Building features: 3 pools, 2-acre spa, fitness center, on-site Cipriani restaurant. "
            "Walking distance to Brickell City Centre mall, Miami Financial District, Metromover. "
            "No foreign buyer restrictions. HOA: $1,850/month (covers cable, internet, water, amenities). "
            "Similar units renting: $4,200–$5,500/month. No state income tax."
        ),
        "features": [
            "Biscayne Bay views", "Sub-Zero/Wolf appliances",
            "3 pools + 2-acre spa", "Brickell City Centre nearby",
            "No foreign buyer restrictions", "No Florida state income tax",
        ],
    },
    {
        "title": "Austin Domain — 3BR Modern Home",
        "address": "8200 Springdale Road, Austin TX 78724",
        "city": "Austin", "state": "TX", "zip": "78724",
        "property_type": "house",
        "bedrooms": 3, "bathrooms": 2, "sqft": 1900,
        "price": 565000,
        "status": "active",
        "description": (
            "Newly built 3-bedroom single-family home 10 min from The Domain — Austin's 2nd downtown. "
            "Open-concept floorplan, quartz countertops, primary suite with walk-in shower, attached 2-car garage. "
            "Backyard with covered patio. HOA $85/month (covers landscaping). "
            "Austin median home price 2025: $525,000. Tech corridor location — major Apple, Tesla, Google campuses nearby. "
            "Excellent rentability: $2,800–$3,400/month. No Texas state income tax."
        ),
        "features": [
            "Near The Domain tech hub", "2-car garage",
            "Open-concept", "No state income tax",
            "Tech employer proximity", "Low HOA",
        ],
    },
    {
        "title": "Nashville Midtown — The Harrison | 2BR Condo",
        "address": "1803 Church St #802, Nashville TN 37203",
        "city": "Nashville", "state": "TN", "zip": "37203",
        "property_type": "apartment",
        "bedrooms": 2, "bathrooms": 2, "sqft": 1100,
        "price": 440000,
        "status": "active",
        "description": (
            "Modern 2/2 in The Harrison — one of Nashville Midtown's boutique luxury buildings. "
            "Floor-to-ceiling windows with Downtown Nashville and Parthenon views. "
            "Hardwood floors, quartz waterfall island, private balcony. "
            "Rooftop deck with Broadway views, concierge, dog park. "
            "5 min walk to Centennial Park and Vanderbilt University. 10 min to Broadway entertainment district. "
            "Nashville median condo 2025: $395,000. Typical rent: $2,400–$3,000/month (yield 6–7%). "
            "No Tennessee state income tax."
        ),
        "features": [
            "Downtown Nashville views", "Rooftop deck",
            "Walk to Vanderbilt", "Near Broadway",
            "Dog-friendly building", "No state income tax",
        ],
    },
]


# ── Knowledge text documents ──────────────────────────────────────────────────

KNOWLEDGE_DOCS = [
    {
        "title": "Pinnacle Property Management — Global Services & FAQ",
        "text": """Pinnacle Property Management — Global Services & FAQ

ABOUT US
Pinnacle Property Management is a full-service international real estate consultancy helping buyers, investors, and tenants across three key markets: the UAE (Dubai & Abu Dhabi), the United Kingdom (London and major UK cities), and the United States (Texas, Florida, Tennessee, and other states). We handle property sales, lettings, property management, and investment advisory under one roof.

Working Hours: Monday–Friday 9:00 AM – 7:00 PM | Saturday 10:00 AM – 5:00 PM | Sunday by appointment
Phone: +971 4 XXX XXXX (UAE) | +44 20 XXXX XXXX (UK) | +1 713 XXX XXXX (US)
Email: info@pinnaclepm.com

BUYER SERVICES
- Full-service buyer representation (no buyer's fee charged in UAE; standard commission in US/UK)
- Property sourcing across all three markets
- Mortgage/finance introduction for UAE, UK, and US properties
- Due diligence: title checks, snagging reports, developer background
- Residency visa advisory for UAE Golden Visa-eligible properties
- Foreign buyer guidance for UK and US markets

SELLER SERVICES
- Professional photography, floor plans, and virtual tours
- Multi-platform marketing (Bayut, Property Finder, Rightmove, Zoopla, Zillow)
- Open-day coordination and offer management
- Completion/transfer coordination with DLD (UAE), Land Registry (UK), or Title Company (US)

PROPERTY MANAGEMENT (LANDLORD SERVICES)
- Tenant sourcing and referencing
- Rent collection and arrears management
- Maintenance coordination (24/7 emergency line)
- Annual inspections and compliance certificates
- UAE: RERA-compliant tenancy agreements (Ejari)
- UK: Gas Safety, EPC, Right to Rent compliance
- US: local landlord-tenant law compliance by state

FAQ — BUYING IN UAE
Q: Can foreigners buy property in Dubai?
A: Yes. Non-UAE nationals can purchase freehold property in designated zones (Marina, Downtown, Palm, JVC, Business Bay, JBR, Dubai Hills, Creek Harbour, etc.). No restrictions on nationality.

Q: What is the Dubai Land Department (DLD) transfer fee?
A: 4% of purchase price, paid at transfer. Buyer typically pays 50% and seller 50% unless negotiated otherwise.

Q: Are there mortgage options for foreign buyers?
A: Yes. UAE banks offer mortgages up to 75% LTV for first-time UAE property buyers (non-residents: typically 60–65% LTV). Interest rates: 4.5–6.5% (2025).

Q: What is the UAE Golden Visa property route?
A: Purchase a property worth AED 2,000,000 or above (from ready — off-plan doesn't qualify) and receive a 10-year UAE residency visa. Extends to spouse and dependent children.

Q: What are typical service charges in Dubai?
A: DIFC/Downtown: AED 20–35/sqft/yr. Marina/JBR: AED 12–18/sqft/yr. JVC/JLT: AED 8–14/sqft/yr. Villas: AED 3–8/sqft/yr.

FAQ — BUYING IN UK
Q: Can overseas buyers purchase property in England & Wales?
A: Yes, no restrictions. Non-residents pay an additional 2% SDLT (Stamp Duty Land Tax) surcharge on top of standard rates.

Q: What is Stamp Duty in the UK (2025)?
A: For residential purchases in England (2025 rates after March 2025 threshold changes):
  - Up to £125,000: 0%
  - £125,001–£250,000: 2%
  - £250,001–£925,000: 5%
  - £925,001–£1.5M: 10%
  - Above £1.5M: 12%
  Additional properties / buy-to-let: +3% on all bands.
  Non-resident surcharge: +2% additional on all bands.

Q: Leasehold vs Freehold in England?
A: Most London flats are leasehold (you own the property for a fixed term, typically 99–999 years). Houses are usually freehold (outright ownership). Scotland uses a different system (equivalent to freehold). Lease lengths below 80 years affect mortgageability.

Q: What is the typical UK mortgage rate for buy-to-let (2025)?
A: UK BTL mortgage rates range from 4.5–6.5% (2025), depending on LTV and lender. Non-UK residents can get mortgages from specialist lenders at 65–70% LTV.

FAQ — BUYING IN US
Q: Can foreigners buy property in the US?
A: Yes, no federal restrictions. Texas, Florida, and Tennessee all welcome international buyers. Note: FIRPTA tax applies to foreign sellers (15% withholding on sale proceeds; net tax may differ).

Q: What are US closing costs?
A: Buyers: 2–5% of purchase price (loan origination, title insurance, escrow fees, property taxes prepaid). Sellers: 6–8% (agent commissions 5–6% + transfer taxes/title).

Q: Texas property taxes?
A: Texas has no state income tax but higher property taxes: typically 1.8–2.8% of assessed value per year. Houston-area properties often assessed 15–25% below market value.
""",
    },
    {
        "title": "UAE Property Market Rates — Dubai & Abu Dhabi 2025",
        "text": """UAE Property Market Rates — Dubai & Abu Dhabi 2025

Market Overview: Dubai's real estate market posted record transaction volumes in 2024 (182,000+ transactions) and continued strongly into 2025. Demand is driven by population growth (Dubai population ~3.8M, 2025), business-friendly tax environment, and Golden Visa programme. Average price growth in prime areas: 8–15% in 2024.

Exchange Rate Reference (July 2025): AED 1 = USD 0.27 | AED 1 = GBP 0.21 | AED 3.67 ≈ USD 1

────────────────────────────────────────────────
DUBAI — SALE PRICES (READY PROPERTIES, Q2 2025)
────────────────────────────────────────────────

DOWNTOWN DUBAI / BURJ KHALIFA AREA
Studio:       AED 850,000 – 1,200,000
1 Bedroom:    AED 1,400,000 – 2,300,000
2 Bedroom:    AED 2,000,000 – 3,800,000
3 Bedroom:    AED 3,500,000 – 6,500,000
Penthouse:    AED 8,000,000 – 50,000,000+

DUBAI MARINA
Studio:       AED 550,000 – 950,000
1 Bedroom:    AED 900,000 – 1,600,000
2 Bedroom:    AED 1,500,000 – 2,800,000
3 Bedroom:    AED 2,500,000 – 5,000,000

PALM JUMEIRAH
1BR Apartment:  AED 2,000,000 – 3,500,000
2BR Apartment:  AED 3,500,000 – 6,500,000
3BR Villa:      AED 14,000,000 – 30,000,000
4BR Signature Villa: AED 22,000,000 – 55,000,000+
Frond villas sell within 2 weeks when priced correctly.

BUSINESS BAY
Studio:       AED 600,000 – 950,000
1 Bedroom:    AED 900,000 – 1,500,000
2 Bedroom:    AED 1,400,000 – 2,400,000

JUMEIRAH BEACH RESIDENCE (JBR)
1 Bedroom:    AED 1,100,000 – 1,800,000
2 Bedroom:    AED 1,700,000 – 3,000,000
3 Bedroom:    AED 2,800,000 – 5,500,000

JUMEIRAH VILLAGE CIRCLE (JVC)
Studio:       AED 380,000 – 620,000
1 Bedroom:    AED 550,000 – 900,000
2 Bedroom:    AED 800,000 – 1,300,000
Best yields in Dubai: 8–10% gross.

JUMEIRAH LAKES TOWERS (JLT)
Studio:       AED 450,000 – 750,000
1 Bedroom:    AED 750,000 – 1,200,000
2 Bedroom:    AED 1,100,000 – 1,900,000

DUBAI HILLS ESTATE
1BR Apartment:    AED 900,000 – 1,400,000
2BR Apartment:    AED 1,500,000 – 2,500,000
3BR Townhouse:    AED 3,200,000 – 4,500,000
4BR Villa:        AED 4,200,000 – 7,500,000

ARABIAN RANCHES (Villas Only)
3 Bedroom:    AED 3,000,000 – 4,500,000
4 Bedroom:    AED 3,500,000 – 6,000,000
5 Bedroom:    AED 5,500,000 – 9,000,000

CREEK HARBOUR
1 Bedroom:    AED 1,200,000 – 1,900,000
2 Bedroom:    AED 1,900,000 – 3,200,000
3 Bedroom:    AED 3,000,000 – 5,000,000
Growth corridor — Emaar's flagship long-term development.

────────────────────────────────────────────────
DUBAI — ANNUAL RENTAL RATES (Q2 2025)
────────────────────────────────────────────────

DOWNTOWN DUBAI
Studio:       AED 65,000 – 95,000/yr
1 Bedroom:    AED 95,000 – 145,000/yr
2 Bedroom:    AED 140,000 – 210,000/yr

DUBAI MARINA
Studio:       AED 55,000 – 80,000/yr
1 Bedroom:    AED 75,000 – 120,000/yr
2 Bedroom:    AED 115,000 – 175,000/yr

PALM JUMEIRAH
1BR Apartment:  AED 140,000 – 200,000/yr
2BR Apartment:  AED 200,000 – 320,000/yr
4BR Villa:      AED 600,000 – 1,000,000/yr
5BR Signature:  AED 900,000 – 1,400,000/yr

BUSINESS BAY
Studio:       AED 45,000 – 70,000/yr
1 Bedroom:    AED 60,000 – 100,000/yr
2 Bedroom:    AED 95,000 – 150,000/yr

JVC
Studio:       AED 30,000 – 48,000/yr
1 Bedroom:    AED 42,000 – 68,000/yr
2 Bedroom:    AED 65,000 – 95,000/yr

────────────────────────────────────────────────
ABU DHABI — SALE PRICES (Q2 2025)
────────────────────────────────────────────────

SAADIYAT ISLAND
Studio:       AED 800,000 – 1,200,000
1 Bedroom:    AED 1,200,000 – 2,200,000
2 Bedroom:    AED 2,500,000 – 4,500,000
Villa 4BR:    AED 7,000,000 – 22,000,000
Premium due to Louvre, Guggenheim, and NYU Abu Dhabi adjacency.

AL REEM ISLAND
Studio:       AED 480,000 – 750,000
1 Bedroom:    AED 750,000 – 1,300,000
2 Bedroom:    AED 1,200,000 – 2,000,000
3 Bedroom:    AED 1,800,000 – 3,000,000

YAS ISLAND
1 Bedroom:    AED 750,000 – 1,200,000
2 Bedroom:    AED 1,200,000 – 2,000,000
3BR Townhouse: AED 2,500,000 – 4,000,000
Near Ferrari World, Yas Waterworld, Yas Mall.

AL RAHA BEACH
2 Bedroom:    AED 1,500,000 – 2,800,000
3 Bedroom:    AED 2,400,000 – 4,500,000
Waterfront lifestyle at lower prices than Dubai Marina.

SHARJAH
2BR Apartment Sale:   AED 350,000 – 750,000
3BR Apartment Sale:   AED 500,000 – 1,000,000
Studio Annual Rent:   AED 14,000 – 28,000/yr
Popular with families seeking affordable UAE base 30 min from Dubai.

────────────────────────────────────────────────
OFF-PLAN vs READY PROPERTY (DUBAI 2025)
────────────────────────────────────────────────
Off-Plan:
+ Typically 15–25% below expected completion price
+ Payment plans: 60/40, 70/30 or post-handover (5 yrs)
+ Dubai Oqood registration: 4% DLD + developer admin fee
- No immediate rental income; timeline risk

Ready:
+ Immediate occupancy or rental income
+ Mortgage-eligible (banks prefer ready)
+ Physical inspection possible
- 4% DLD transfer fee on full price
""",
    },
    {
        "title": "UK Property Market Rates — London and Key Cities 2025",
        "text": """UK Property Market Rates — London and Key Cities 2025

Market Overview (2025): After Bank of England rate cuts (base rate 4.75% as of early 2025, with further cuts expected), UK transaction volumes are recovering. Average UK house price: £285,000 (nationwide, Q1 2025). London remains the most expensive market. Yields strongest in Manchester, Leeds, Liverpool, and Birmingham.

Exchange Rate Reference (July 2025): GBP 1 = USD 1.27 | GBP 1 = EUR 1.18 | GBP 1 = AED 4.67

────────────────────────────────────────────────
LONDON — SALE PRICES (Q2 2025)
────────────────────────────────────────────────

ZONE 1 — PRIME CENTRAL LONDON
(Mayfair, Knightsbridge, Chelsea, Belgravia, Kensington)
Studio / 1BR:     £600,000 – 1,500,000
2 Bedroom:        £900,000 – 3,000,000
3 Bedroom:        £1,500,000 – 6,000,000
Penthouse/House:  £5,000,000 – 50,000,000+
These areas are stable stores of value and attract UHNWIs.

ZONE 1 — CITY OF LONDON / CANARY WHARF
1 Bedroom:    £450,000 – 800,000
2 Bedroom:    £700,000 – 1,200,000
3 Bedroom:    £1,000,000 – 2,000,000
Strong rental demand from financial sector workers.

ZONE 2 — POPULAR AREAS
(Battersea/Nine Elms, Shoreditch, Hackney, Clapham, Islington)
1 Bedroom:    £400,000 – 700,000
2 Bedroom:    £600,000 – 1,100,000
3 Bedroom:    £800,000 – 1,800,000
Nine Elms (US Embassy area): active regeneration corridor, strong capital growth.

ZONE 3–4 — COMMUTER ZONES
(Richmond, Wimbledon, Ealing, Lewisham, Woolwich)
1 Bedroom:    £280,000 – 450,000
2 Bedroom:    £380,000 – 650,000
3BR House:    £500,000 – 900,000
Good family areas with schools and green space.

────────────────────────────────────────────────
LONDON — MONTHLY RENTAL RATES (Q2 2025)
────────────────────────────────────────────────

Zone 1 (Prime):
Studio:       £2,000 – 3,500/month
1 Bedroom:    £2,800 – 5,500/month
2 Bedroom:    £4,000 – 8,500/month

Zone 1 (City/Canary Wharf):
1 Bedroom:    £2,200 – 3,500/month
2 Bedroom:    £3,200 – 4,800/month

Zone 2:
1 Bedroom:    £1,800 – 2,800/month
2 Bedroom:    £2,400 – 3,800/month

Zone 3–4:
1 Bedroom:    £1,300 – 2,000/month
2 Bedroom:    £1,700 – 2,600/month
3BR House:    £2,200 – 3,500/month

────────────────────────────────────────────────
UK REGIONAL CITIES — SALE PRICES (Q2 2025)
────────────────────────────────────────────────

MANCHESTER CITY CENTRE
Studio:       £140,000 – 210,000
1 Bedroom:    £180,000 – 300,000
2 Bedroom:    £240,000 – 420,000
3BR House (suburbs): £280,000 – 450,000
BTL yields: 6–8%. Top investor market in UK outside London.

BIRMINGHAM CITY CENTRE
Studio:       £130,000 – 200,000
1 Bedroom:    £160,000 – 280,000
2 Bedroom:    £200,000 – 360,000
3BR Semi-detached: £220,000 – 375,000
Commonwealth Games legacy and HSBC HQ relocation driving demand.

EDINBURGH
City Centre 1BR:    £220,000 – 380,000
City Centre 2BR:    £300,000 – 520,000
New Town 3BR flat:  £450,000 – 750,000
Detached house:     £500,000 – 1,500,000+
High STR demand; STL licences tightening — act fast if short-term letting is your plan.

GLASGOW
1 Bedroom:    £110,000 – 200,000
2 Bedroom:    £150,000 – 280,000
3BR House:    £180,000 – 350,000
BTL yields: 7–9%. Most affordable major UK city.

BRISTOL
1 Bedroom:    £230,000 – 380,000
2 Bedroom:    £300,000 – 500,000
3BR Terraced: £380,000 – 650,000
Clifton: £700,000 – 1,200,000 for larger houses.
Tech hub (aerospace and digital), strong rental demand from graduates.

LEEDS
1 Bedroom:    £140,000 – 230,000
2 Bedroom:    £170,000 – 310,000
3BR Semi:     £200,000 – 380,000
BTL yields: 6–8%. Major financial services and medical research hub.

────────────────────────────────────────────────
UK — STAMP DUTY LAND TAX (SDLT) 2025
────────────────────────────────────────────────
(England & Northern Ireland — rates from April 2025)
Residential Purchase:
  Up to £125,000:       0%
  £125,001–£250,000:    2%
  £250,001–£925,000:    5%
  £925,001–£1,500,000:  10%
  Over £1,500,000:      12%

Additional property surcharge (BTL / second home): +3% on ALL bands.
Non-UK resident surcharge: +2% on ALL bands.
First-time buyer relief: 0% up to £425,000 (on primary residence only, property value ≤ £625,000).

Example: Non-resident buying a £550,000 London flat (BTL):
  0% on £125K + 2% on £125K + 5% on £300K = £0 + £2,500 + £15,000 = £17,500 standard SDLT
  + 3% surcharge on £550K = £16,500
  + 2% non-resident surcharge on £550K = £11,000
  Total SDLT: £45,000

Scotland uses Land & Buildings Transaction Tax (LBTT) with different rates.
""",
    },
    {
        "title": "US Property Market Rates — Key Cities 2025",
        "text": """US Property Market Rates — Key Cities 2025

Market Overview (2025): US 30-year fixed mortgage rates sit at 6.5–7.2% (Q2 2025) after Fed rate cuts from the 2023 highs. Inventory remains tight in Sun Belt markets. No restrictions on foreign buyers at the federal level, though some states have enacted restrictions on purchases by nationals of specific countries (FL, TX — buyers should confirm eligibility).

Exchange Rate Reference (July 2025): USD 1 = AED 3.67 | USD 1 = GBP 0.79

────────────────────────────────────────────────
HOUSTON, TEXAS — PINNACLE'S HOME MARKET
────────────────────────────────────────────────

Houston is the 4th largest US city (pop. 2.4M city / 7.3M metro). No state income tax. Diverse economy: energy, medical (Texas Medical Center — world's largest), aerospace (NASA), and finance.

SALE PRICES (Q2 2025):
Inner Loop / Midtown / Heights / Montrose / Museum District:
  Studio/1BR condo:   $250,000 – $550,000
  2BR condo:          $350,000 – $700,000
  3BR townhome:       $450,000 – $900,000
  3BR house:          $500,000 – $1,000,000

Galleria / River Oaks:
  2BR condo:          $350,000 – $800,000
  3BR house:          $600,000 – $1,500,000
  4BR luxury house:   $900,000 – $3,000,000

Suburbs — Katy, Sugar Land, Pearland, Cypress, The Woodlands:
  3BR house:          $320,000 – $600,000
  4BR house:          $400,000 – $800,000
  5BR executive:      $600,000 – $1,200,000
  The Woodlands premium: 20–30% above typical suburb.

RENTAL RATES (Q2 2025):
1BR apartment:    $1,200 – $1,900/month
2BR apartment:    $1,500 – $2,600/month
3BR house:        $2,000 – $3,500/month (suburbs lower, inner-loop higher)

Property Taxes: 1.8–2.8% of assessed value/year (Harris County).
Homeowner's Insurance: $1,500–$3,500/year (high due to hurricane risk).
No HOA for single-family except in master-planned communities ($50–$250/month).

────────────────────────────────────────────────
MIAMI / SOUTH FLORIDA
────────────────────────────────────────────────

Miami market hit all-time highs in 2022–2023, stabilised in 2024–2025 with more inventory.
No state income tax. Popular with Latin American buyers and remote workers.

SALE PRICES (Q2 2025):
Brickell (financial district):
  Studio:         $350,000 – $600,000
  1 Bedroom:      $480,000 – $900,000
  2 Bedroom:      $650,000 – $1,400,000
  Penthouse:      $2,000,000 – $10,000,000+

Miami Beach / South Beach:
  1 Bedroom:      $550,000 – $1,200,000
  2 Bedroom:      $900,000 – $2,500,000
  3BR Penthouse:  $2,500,000 – $8,000,000+

Edgewater / Wynwood / Midtown:
  1 Bedroom:      $400,000 – $700,000
  2 Bedroom:      $600,000 – $1,100,000
  (Emerging arts districts, strong growth corridor)

Fort Lauderdale / Aventura:
  1 Bedroom:      $280,000 – $550,000
  2 Bedroom:      $380,000 – $750,000
  Waterfront single-family: $800,000 – $5,000,000+

HOA fees: $800–$3,500/month in high-end towers.
Property Tax: ~2.0–2.5% assessed value (Dade County).

────────────────────────────────────────────────
NEW YORK CITY
────────────────────────────────────────────────

SALE PRICES (Q2 2025):
Manhattan — Midtown / Upper East Side / Upper West Side:
  Studio:         $600,000 – $1,000,000
  1 Bedroom:      $800,000 – $2,000,000
  2 Bedroom:      $1,500,000 – $4,500,000
  3 Bedroom:      $2,500,000 – $8,000,000+

Brooklyn — Park Slope / Williamsburg / DUMBO:
  1 Bedroom:      $650,000 – $1,200,000
  2 Bedroom:      $900,000 – $1,900,000
  3BR Townhouse:  $1,500,000 – $3,500,000

Queens — Astoria / Long Island City:
  1 Bedroom:      $450,000 – $750,000
  2 Bedroom:      $650,000 – $1,100,000

RENTAL RATES (Q2 2025):
Manhattan Studio:     $2,500 – $4,500/month
Manhattan 1BR:        $3,500 – $6,500/month
Manhattan 2BR:        $5,000 – $10,000/month
Brooklyn 1BR:         $2,500 – $4,500/month

NYC Mansion Tax: 1% on sales $1M–$2M, scaling to 3.9% over $25M.
NYC Transfer Tax + State Transfer Tax: ~1.8–1.9% of sale price.

────────────────────────────────────────────────
AUSTIN, TEXAS
────────────────────────────────────────────────

Tech-hub boom post-2020; market corrections of 10–15% from 2022 peak; now stabilised.
No state income tax. Population growth among fastest in US.

SALE PRICES (Q2 2025):
Downtown / East Austin:
  1BR condo:      $380,000 – $650,000
  2BR condo:      $500,000 – $900,000
  3BR house:      $650,000 – $1,200,000

Round Rock / Cedar Park / Pflugerville (suburbs):
  3BR house:      $350,000 – $550,000
  4BR house:      $420,000 – $700,000

The Domain area (tech campus belt):
  2BR:            $400,000 – $700,000
  3BR house:      $520,000 – $850,000
  Close to Apple ($1B campus), Tesla, Oracle, Google offices.

Property Tax: ~1.8–2.4% assessed value. No income tax.

────────────────────────────────────────────────
CHICAGO, ILLINOIS
────────────────────────────────────────────────

Stable Midwest market. Excellent price-to-rent ratio for investors.

SALE PRICES (Q2 2025):
Gold Coast / Lincoln Park / Lakeview:
  1BR condo:      $280,000 – $550,000
  2BR condo:      $400,000 – $800,000
  3BR house:      $700,000 – $1,500,000

River North / Streeterville / West Loop:
  1BR:            $320,000 – $600,000
  2BR:            $480,000 – $950,000

Oak Park / Evanston (suburbs):
  3BR house:      $350,000 – $650,000
  4BR house:      $450,000 – $850,000

BTL Yield: 5–7% in city neighborhoods.
Property Tax: 2.0–3.5% (Cook County — among highest in US).
State income tax: 4.95% (Illinois flat rate).

────────────────────────────────────────────────
NASHVILLE, TENNESSEE
────────────────────────────────────────────────

One of the fastest-growing cities in the US. No state income tax.
Major corporate relocations: Oracle HQ, Amazon, AllianceBernstein.

SALE PRICES (Q2 2025):
Midtown / 12 South / East Nashville:
  1BR condo:      $320,000 – $550,000
  2BR condo:      $420,000 – $750,000
  3BR house:      $550,000 – $950,000

Franklin / Brentwood (premium suburbs):
  3BR house:      $550,000 – $900,000
  4BR house:      $700,000 – $1,400,000

Rental Rates:
1BR:    $1,500 – $2,200/month
2BR:    $2,000 – $3,000/month
BTL yields: 5.5–7.5%. Strong short-term rental market (music tourism).

────────────────────────────────────────────────
US BUYING PROCESS OVERVIEW
────────────────────────────────────────────────
1. Pre-approval for mortgage (or proof of funds for cash buyers)
2. Make offer → negotiate → sign Purchase & Sale Agreement
3. Inspection period (typically 10 days)
4. Title search and insurance
5. Closing (~30–45 days from accepted offer)
6. Closing costs: 2–5% for buyers, 6–8% for sellers
7. No restrictions for foreign buyers at federal level (verify state rules for nationals of China, Russia, Iran — some Florida/Texas restrictions apply)
8. Foreign buyers: ITIN (Individual Taxpayer ID) needed for tax filings; no Social Security Number required to buy.
""",
    },
]


# ── Main seeding logic ────────────────────────────────────────────────────────

async def reingest_existing_properties(company_id: str) -> None:
    """Re-embed all existing Supabase properties into Qdrant (for prod which has empty Qdrant)."""
    from app.dependencies import get_supabase_admin
    from app.properties.models import property_to_text
    from app.rag.pipeline import ingest_text

    sb = get_supabase_admin()
    props = sb.table("properties").select("*").eq("company_id", company_id).execute()
    rows = props.data or []
    print(f"Re-ingesting {len(rows)} existing properties into Qdrant...")
    for p in rows:
        text = property_to_text(p)
        await ingest_text(
            text=text,
            company_id=company_id,
            metadata={
                "source_type": "property_form",
                "property_id": p["id"],
                "doc_category": "listing",
                "filename": f"property_{p['id'][:8]}.txt",
            },
        )
        print(f"  ✓ {p.get('title', p['id'][:8])}")


async def add_new_properties(company_id: str) -> list[str]:
    """Insert new UAE/UK/US properties into Supabase (returns new IDs)."""
    from app.dependencies import get_supabase_admin

    sb = get_supabase_admin()
    new_ids = []
    print(f"Inserting {len(NEW_PROPERTIES)} new properties into Supabase...")
    for p in NEW_PROPERTIES:
        row = dict(p)
        row["company_id"] = company_id
        # Convert Decimal/float fields
        if row.get("price") is not None:
            row["price"] = float(row["price"])
        try:
            result = sb.table("properties").insert(row).execute()
            pid = result.data[0]["id"]
            new_ids.append(pid)
            print(f"  ✓ Supabase: {p['title'][:60]}")
        except Exception as e:
            print(f"  ✗ {p['title'][:60]}: {e}")
    return new_ids


async def ingest_new_properties(company_id: str, property_ids: list[str]) -> None:
    """Embed newly added properties into Qdrant."""
    from app.dependencies import get_supabase_admin
    from app.properties.models import property_to_text
    from app.rag.pipeline import ingest_text

    sb = get_supabase_admin()
    print(f"Ingesting {len(property_ids)} new properties into Qdrant...")
    for pid in property_ids:
        try:
            result = sb.table("properties").select("*").eq("id", pid).single().execute()
            p = result.data
            if not p:
                print(f"  ✗ Property {pid[:8]} not found in Supabase")
                continue
            text = property_to_text(p)
            await ingest_text(
                text=text,
                company_id=company_id,
                metadata={
                    "source_type": "property_form",
                    "property_id": pid,
                    "doc_category": "listing",
                    "filename": f"property_{pid[:8]}.txt",
                },
            )
            print(f"  ✓ Qdrant: {p.get('title', pid[:8])[:60]}")
        except Exception as e:
            print(f"  ✗ {pid[:8]}: {e}")


async def ingest_knowledge_docs(company_id: str) -> None:
    """Ingest market knowledge text documents into Qdrant."""
    from app.rag.pipeline import ingest_text

    print(f"Ingesting {len(KNOWLEDGE_DOCS)} knowledge documents into Qdrant...")
    for doc in KNOWLEDGE_DOCS:
        try:
            result = await ingest_text(
                text=doc["text"],
                company_id=company_id,
                metadata={
                    "source_type": "text_paste",
                    "doc_category": "market_data",
                    "filename": doc["title"],
                },
            )
            chunks = result.get("chunk_count", "?")
            print(f"  ✓ {doc['title'][:60]} ({chunks} chunks)")
        except Exception as e:
            print(f"  ✗ {doc['title'][:60]}: {e}")


async def show_qdrant_summary(company_id: str) -> None:
    from qdrant_client import AsyncQdrantClient
    from collections import Counter
    client = AsyncQdrantClient(host="qdrant", port=6333)
    info = await client.get_collection("nexadesk_kb")
    results, _ = await client.scroll(
        "nexadesk_kb", limit=500, with_payload=True, with_vectors=False,
    )
    filenames = [r.payload.get("filename", "?") for r in results if r.payload.get("company_id") == company_id]
    print(f"\nQdrant summary for company {company_id[:8]}:")
    print(f"  Total points: {info.points_count}")
    for fname, count in Counter(filenames).most_common():
        print(f"  {count:3d} chunks  {fname}")
    await client.close()


async def _bootstrap_qdrant() -> None:
    """Initialize the module-level Qdrant client (normally done by FastAPI lifespan)."""
    from app.dependencies import get_qdrant, ensure_collection
    from app.config import get_settings
    s = get_settings()
    client = await get_qdrant(s)
    await ensure_collection(client, s)
    print(f"Qdrant ready: {s.QDRANT_HOST}:{s.QDRANT_PORT}  collection={s.QDRANT_COLLECTION}")


async def main(qdrant_only: bool, reingest_existing: bool) -> None:
    print("=" * 60)
    print("NexaDesk Knowledge Base Seeder")
    print("=" * 60)

    await _bootstrap_qdrant()

    if reingest_existing or not qdrant_only:
        await reingest_existing_properties(COMPANY_ID)

    if not qdrant_only:
        new_ids = await add_new_properties(COMPANY_ID)
    else:
        # In qdrant-only mode, fetch IDs of any properties NOT yet in Qdrant
        from app.dependencies import get_supabase_admin
        sb = get_supabase_admin()
        props = sb.table("properties").select("id").eq("company_id", COMPANY_ID).execute()
        all_ids = [p["id"] for p in (props.data or [])]
        # We'll ingest all — duplicates in Qdrant are fine (upsert by UUID)
        new_ids = all_ids[10:]  # skip first 10 (already re-ingested in reingest_existing)

    if new_ids:
        await ingest_new_properties(COMPANY_ID, new_ids)

    await ingest_knowledge_docs(COMPANY_ID)
    await show_qdrant_summary(COMPANY_ID)
    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qdrant-only",
        action="store_true",
        help="Skip Supabase inserts (already done). Only ingest into Qdrant.",
    )
    parser.add_argument(
        "--reingest-existing",
        action="store_true",
        help="Re-embed the 10 existing Houston properties even in qdrant-only mode.",
    )
    args = parser.parse_args()
    asyncio.run(main(qdrant_only=args.qdrant_only, reingest_existing=args.reingest_existing))

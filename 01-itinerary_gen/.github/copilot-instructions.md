# Copilot Instructions — AI Itinerary Builder

## Project overview

This is an **AI-powered travel itinerary builder** for a travel agency. The system accepts a natural-language trip request (e.g. _"5 days Japan cherry blossom trip for 2 people, budget $8,000 AUD"_), queries a live inventory database of flights, hotels, and activities, and returns a fully structured JSON itinerary preset that feeds directly into the frontend itinerary builder page.

The AI's role is **curation and sequencing**, not invention. It selects real records from filtered inventory and arranges them into a coherent day-by-day plan. It must never fabricate flight IDs, hotel IDs, prices, or any field not present in the provided inventory context.

---

## Repository structure

```
/
├── mock_fc.py                  # Mock data generator — run once to seed CSVs
├── itinerary_engine.py         # Core AI pipeline — backend entry point
├── flights_intl_v2.csv         # Generated flight inventory (2,500 records)
├── accommodation_intl_v2.csv   # Generated hotel inventory (2,500 records)
├── activities_intl_v2.csv      # Generated activities inventory (2,500 records)
├── itinerary_builder_demo.html # Full browser demo (standalone, no server needed)
└── .github/
    └── copilot-instructions.md # This file
```

---

## Architecture: the 5-step pipeline

Every itinerary generation request flows through these steps in order. Keep this contract intact when modifying the codebase.

```
User input (natural language)
        │
        ▼
[Step 1] parse_user_request()
   Regex + keyword maps → structured params dict
   { destinations, duration_days, theme, budget_aud,
     group_size, cabin_class, min_stars, origin }
        │
        ▼
[Step 2] query_inventory()
   Filter CSVs / DB by params → candidate inventory
   { outbound_flights[], inbound_flights[],
     inter_city_legs[], hotel_options{}, activity_options{} }
        │
        ▼
[Step 3] build_ai_prompt()
   Compose system prompt + user prompt
   Inject filtered inventory as JSON context
   Embed strict output schema
        │
        ▼
[Step 4] call_llm()           ← LLM provider is swappable here (see below)
   Send prompt → receive raw JSON string
        │
        ▼
[Step 5] validate_itinerary()
   Parse JSON, verify required keys,
   recalculate budget totals, flag warnings/errors
        │
        ▼
Structured itinerary JSON (preset for builder page)
```

---

## Output JSON schema

The AI must always return a JSON object matching this exact schema. Do not add, remove, or rename top-level keys.

```jsonc
{
  "meta": {
    "trip_id": "<uuid-v4>",
    "created_at": "<ISO 8601 datetime>",
    "version": "1.0"
  },
  "trip": {
    "title": "<engaging trip title>",
    "destination_cities": ["<city>"],
    "duration_days": 5,
    "theme": "<theme string>",
    "travel_dates": {
      "depart_date": "YYYY-MM-DD",
      "return_date": "YYYY-MM-DD"
    },
    "total_cost_aud": 0.0,
    "currency": "AUD",
    "group_size": 2,
    "status": "draft"
  },
  "description": "<human-readable markdown itinerary — intro + ## Day N sections>",
  "flights": [
    {
      "flight_id": "<exact ID from inventory e.g. INT-FL-00017>",
      "leg": "outbound | return | inter-city",
      "airline": "",
      "origin": "",
      "destination": "",
      "departure_datetime": "YYYY-MM-DD HH:MM",
      "arrival_datetime": "YYYY-MM-DD HH:MM",
      "cabin_class": "Economy | Business | First",
      "price_aud": 0.0,
      "seats_available": 0,
      "booking_class": "Saver | Flex | Premium",
      "stops": 0,
      "baggage_kg": 20,
      "refundable": false
    }
  ],
  "accommodation": [
    {
      "hotel_id": "<exact ID from inventory e.g. INT-HT-00043>",
      "hotel_name": "",
      "city": "",
      "star_rating": 5,
      "room_type": "Standard | Deluxe | Suite",
      "price_per_night_aud": 0.0,
      "nights": 4,
      "total_price_aud": 0.0,
      "check_in": "YYYY-MM-DD",
      "check_out": "YYYY-MM-DD",
      "amenities": "wifi,pool,spa",
      "breakfast_included": false,
      "cancellation_policy": "Free | Partial | Non-refundable"
    }
  ],
  "days": [
    {
      "day_number": 1,
      "date": "YYYY-MM-DD",
      "city": "",
      "title": "<e.g. Arrival & Shibuya Exploration>",
      "description": "<2-3 sentence narrative>",
      "activities": [
        {
          "activity_id": "<exact ID from inventory e.g. INT-AC-00678>",
          "activity_name": "",
          "category": "Culture | Adventure | Food | Romance | Luxury",
          "start_time": "HH:MM",
          "duration_hours": 3,
          "price_aud": 0.0,
          "rating": 4.9,
          "notes": "<practical tip>"
        }
      ]
    }
  ],
  "budget_breakdown": {
    "flights_aud": 0.0,
    "accommodation_aud": 0.0,
    "activities_aud": 0.0,
    "estimated_meals_aud": 0.0,
    "estimated_transport_aud": 0.0,
    "total_aud": 0.0
  },
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  }
}
```

**Validation rules enforced post-generation:**
- All IDs must exist verbatim in the inventory passed in the prompt
- `days` array length must equal `trip.duration_days`
- `budget_breakdown.total_aud` must equal the sum of all five sub-fields (auto-corrected if off by >$10)
- `accommodation[].total_price_aud` must equal `price_per_night_aud × nights`
- `trip.total_cost_aud` must match `budget_breakdown.total_aud`

---

## Data model: inventory fields

### flights_intl_v2.csv

| Field | Type | Notes |
|---|---|---|
| `flight_id` | string | Primary key e.g. `INT-FL-00017` |
| `airline` | string | Emirates, Delta, Singapore Airlines, British Airways, Lufthansa, Qatar Airways |
| `origin` | string | City name |
| `origin_country` | string | |
| `destination` | string | City name |
| `destination_country` | string | |
| `departure_datetime` | string | `YYYY-MM-DD HH:MM` |
| `arrival_datetime` | string | `YYYY-MM-DD HH:MM` |
| `duration_minutes` | int | |
| `stops` | int | 0 = direct |
| `cabin_class` | string | Economy / Business / First |
| `price_aud` | int | Base: Economy $600, Business $2500, First $6000 |
| `seats_available` | int | Filter: `>= group_size` |
| `booking_class` | string | Saver / Flex / Premium |
| `baggage_kg` | int | 15, 20, 23, or 30 |
| `refundable` | bool | |
| `dest_themes` | string | Comma-separated, e.g. `culture,food,urban,adventure,seasonal` |
| `dest_best_months` | string | Comma-separated month numbers e.g. `3,4,10,11` |

### accommodation_intl_v2.csv

| Field | Type | Notes |
|---|---|---|
| `hotel_id` | string | Primary key e.g. `INT-HT-00043` |
| `hotel_name` | string | Brand + city |
| `city` | string | |
| `country` | string | |
| `property_type` | string | Hotel / Resort / Boutique |
| `star_rating` | int | 3–5 |
| `room_type` | string | Standard / Deluxe / Suite |
| `price_per_night_aud` | int | `(stars × 120) + rand(0–500)` |
| `max_guests` | int | Filter: `>= group_size` |
| `amenities` | string | Comma-separated |
| `breakfast_included` | bool | |
| `cancellation_policy` | string | Free / Partial / Non-refundable |
| `min_nights` | int | Minimum stay requirement |
| `availability_start` | string | `2026-01-01` |
| `availability_end` | string | `2026-12-31` |
| `theme_tags` | string | Comma-separated, derived from city themes + star rating |
| `best_months` | string | Comma-separated month numbers |

### activities_intl_v2.csv

| Field | Type | Notes |
|---|---|---|
| `activity_id` | string | Primary key e.g. `INT-AC-00678` |
| `activity_name` | string | City + activity type |
| `city` | string | |
| `country` | string | |
| `category` | string | Adventure / Culture / Food / Romance / Luxury |
| `duration_hours` | int | 1–8 |
| `price_aud` | int | 50–600 |
| `rating` | float | 4.0–5.0 |
| `suitable_for` | string | Solo / Couple / Group / Family |
| `difficulty` | string | Easy / Moderate / Challenging |
| `min_age` | int | |
| `group_size_max` | int | Filter: `>= group_size` |
| `booking_lead_days` | int | Days advance booking required |
| `availability` | string | Year-round |
| `theme_tags` | string | City themes + activity category |
| `best_months` | string | Comma-separated month numbers |

---

## Supported destinations (mock data)

The mock dataset covers 20 cities. Destination parsing maps aliases to canonical city names:

| User says | Maps to | Country |
|---|---|---|
| japan, tokyo, kyoto | Tokyo | Japan |
| paris, france | Paris | France |
| dubai, uae | Dubai | UAE |
| singapore | Singapore | Singapore |
| london, uk | London | UK |
| new york, nyc | New York | USA |
| bali, thailand, bangkok | Bangkok | Thailand |
| rome, italy | Rome | Italy |
| barcelona, spain | Barcelona | Spain |
| berlin, germany | Berlin | Germany |
| seoul, korea | Seoul | South Korea |
| amsterdam | Amsterdam | Netherlands |
| istanbul | Istanbul | Turkey |
| hong kong | Hong Kong | China |
| cape town, south africa | Cape Town | South Africa |
| zurich, switzerland | Zurich | Switzerland |
| mumbai, india | Mumbai | India |
| toronto, canada | Toronto | Canada |
| los angeles, usa | Los Angeles | USA |
| san francisco | San Francisco | USA |

---

## Supported themes and their defaults

| Theme | Cabin default | Min stars | Triggered by keywords |
|---|---|---|---|
| `luxury` | First | 5 | luxury, premium, 5-star, five star, high-end, first class |
| `budget` | Economy | 3 | budget, cheap, affordable, backpacker, low-cost |
| `adventure` | Economy | 3 | adventure, hiking, outdoor, extreme, trek, diving |
| `romance` | Business | 4 | romance, romantic, honeymoon, couples, anniversary |
| `culture` | Economy | 3 | culture, history, museum, heritage, art, historic |
| `food` | Economy | 3 | food, culinary, gastronomy, eat, cuisine, foodie |
| `family` | Economy | 3 | family, kids, children, child-friendly |
| `beach` | Economy | 3 | beach, island, coast, sea, ocean, surf |
| `seasonal` | Economy | 3 | cherry blossom, sakura, autumn leaves, foliage, festival |

---

## Swapping the LLM: replacing Claude with Gemini Flash 2.5

The LLM call is isolated to a single function `call_llm()` (previously `call_claude()`). To use Google Gemini Flash 2.5 (free tier via Google AI Studio), replace that function only. Nothing else in the pipeline changes.

### 1. Install the SDK

```bash
pip install google-generativeai
```

### 2. Get a free API key

Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — free tier includes Gemini 2.5 Flash with generous rate limits (no credit card required).

### 3. Set your environment variable

```bash
export GEMINI_API_KEY="your-key-here"
```

Or in `.env`:
```
GEMINI_API_KEY=your-key-here
```

### 4. Replace `call_claude()` with `call_gemini()`

In `itinerary_engine.py`, replace the import and function:

```python
# REMOVE this:
import anthropic

# ADD this:
import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-2.5-flash"   # free tier model

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Send prompt to Gemini Flash and return the raw text response."""
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.3,          # lower = more deterministic JSON
            max_output_tokens=4096,
            response_mime_type="application/json",  # forces JSON output mode
        )
    )
    response = model.generate_content(user_prompt)
    return response.text
```

### 5. Update the orchestrator call

In `generate_itinerary()`, change:
```python
# BEFORE
raw_response = call_claude(SYSTEM_PROMPT, user_prompt)

# AFTER
raw_response = call_llm(SYSTEM_PROMPT, user_prompt)
```

### 6. Notes on Gemini JSON mode

Gemini 2.5 Flash supports `response_mime_type="application/json"` which forces structured output. This makes `response.text` return clean JSON without markdown fences — remove the fence-stripping logic in `parse_llm_response()` if you want, but keeping it is harmless.

If using the **REST API directly** instead of the SDK (e.g. in a browser/frontend):

```javascript
const response = await fetch(
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: systemPrompt }] },
      contents: [{ parts: [{ text: userPrompt }] }],
      generationConfig: {
        temperature: 0.3,
        maxOutputTokens: 4096,
        responseMimeType: "application/json"
      }
    })
  }
);
const data = await response.json();
const rawText = data.candidates[0].content.parts[0].text;
```

### 7. Other free LLM options

The same swap pattern works for any OpenAI-compatible API:

| Provider | Free model | SDK swap |
|---|---|---|
| Google AI Studio | `gemini-2.5-flash` | `google-generativeai` (above) |
| Groq | `llama-3.3-70b-versatile` | `openai` SDK, base_url=`https://api.groq.com/openai/v1` |
| OpenRouter | `mistralai/mistral-7b-instruct:free` | `openai` SDK, base_url=`https://openrouter.ai/api/v1` |
| Ollama (local) | `llama3.2`, `mistral` | `openai` SDK, base_url=`http://localhost:11434/v1` |

**Generic OpenAI-compatible adapter** (works for Groq, OpenRouter, Ollama):

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],   # or "ollama" for local
    base_url=os.environ["LLM_BASE_URL"]  # provider-specific endpoint
)

def call_llm(system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        temperature=0.3,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        response_format={"type": "json_object"}  # if supported by provider
    )
    return response.choices[0].message.content
```

---

## System prompt (canonical)

This system prompt is defined as `SYSTEM_PROMPT` in `itinerary_engine.py`. Do not shorten it — every rule is load-bearing.

```
You are an expert travel itinerary planner for a travel agency system.
Your role is to select the best flights, hotels, and activities from the
provided inventory and generate a complete, structured travel itinerary.

CRITICAL RULES:
1. You MUST return ONLY a single valid JSON object — no markdown, no explanation, no code fences.
2. All IDs (flight_id, hotel_id, activity_id) MUST come from the provided inventory exactly as-is.
3. Do NOT invent prices, IDs, or properties not in the inventory.
4. The "description" field is a beautifully written, human-readable markdown itinerary with:
   - An engaging introduction paragraph
   - A day-by-day plan using markdown headers (## Day 1, etc.)
   - Practical tips and highlights for each day
5. Budget_breakdown.total_aud must equal the sum of all selected flights + accommodation + activities.
6. validation.warnings should flag: tight budgets, limited availability, long transit days.
7. validation.errors should flag: missing required inventory (no flights found, no hotels available).
8. Select options that best match the travel theme, budget, and group size.
9. Days array must have exactly duration_days entries.
```

---

## Inventory query logic (Step 2)

The filtering strategy before sending data to the LLM:

```python
# Flights: filter by route, cabin class, and seat availability
outbound = flights_df[
    (flights_df["origin"].str.lower() == origin.lower()) &
    (flights_df["destination"] == destination) &
    (flights_df["cabin_class"] == cabin_class) &
    (flights_df["seats_available"] >= group_size)
].sort_values("price_aud").head(5)

# Hotels: filter by city, star rating, capacity; theme-sorted
hotels = hotels_df[
    (hotels_df["city"] == city) &
    (hotels_df["star_rating"] >= min_stars) &
    (hotels_df["max_guests"] >= group_size)
].sort_values(["star_rating", "price_per_night_aud"], ascending=[False, True]).head(4)

# Activities: theme-boosted sort — matching theme_tags floated to top
theme_match = activities_df["theme_tags"].str.contains(theme, na=False)
themed = activities_df[theme_match & (activities_df["city"] == city)]\
    .sort_values("rating", ascending=False).head(6)
```

**Token budget awareness:** the prompt sends at most 5 outbound flights + 5 return flights + 4 hotels + 6 activities per city = ~20 records. Each record is ~200–400 tokens. Total inventory context stays under 8,000 tokens, well within all free tier limits.

---

## Adding a new destination

1. Add the city to `CITY_COUNTRY_MAP` in `mock_fc.py`
2. Add theme tags to `CITY_THEMES`
3. Add best months to `CITY_BEST_MONTHS`
4. Add alias mapping to `CITY_ALIASES` in `parse_user_request()`
5. Re-run `python mock_fc.py` to regenerate the CSVs
6. If using the demo HTML, rebuild `INVENTORY_DATA` by running the extraction snippet from the project build log

---

## Adding a new travel theme

1. Add keyword list to `THEME_KEYWORDS` in `itinerary_engine.py`
2. Optionally add cabin default to `CABIN_THEME_MAP`
3. Optionally add hotel star default to `STAR_THEME_MAP`
4. Add theme to city theme tag arrays in `CITY_THEMES` in `mock_fc.py` if applicable
5. Re-run `mock_fc.py` to regenerate CSVs with updated `theme_tags`

---

## Connecting to a real database

Replace the three `pd.read_csv(...)` calls in `query_inventory()` with your ORM queries. The pandas filter chains become SQL WHERE clauses:

```python
# Example: SQLAlchemy equivalent of the flight filter
outbound = db.query(Flight).filter(
    Flight.origin.ilike(origin),
    Flight.destination == destination,
    Flight.cabin_class == cabin_class,
    Flight.seats_available >= group_size,
    Flight.departure_datetime >= today
).order_by(Flight.price_aud).limit(5).all()
```

The rest of the pipeline (Steps 3–5) is unchanged. Convert ORM objects to dicts before passing to `build_ai_prompt()`.

---

## Frontend integration

The demo (`itinerary_builder_demo.html`) is self-contained with inventory embedded. For production:

1. The backend `generate_itinerary()` is exposed as a POST endpoint: `POST /api/itinerary/generate`
2. Request body: `{ "user_input": "...", "origin_city": "Sydney" }`
3. Response: the full itinerary JSON (schema above)
4. The frontend itinerary builder page receives this JSON as its initial state (preset)
5. All fields are editable — the JSON `status: "draft"` signals this is a modifiable preset, not a confirmed booking

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes (if using Gemini) | Google AI Studio key |
| `ANTHROPIC_API_KEY` | Yes (if using Claude) | Anthropic API key |
| `LLM_API_KEY` | Yes (if using generic adapter) | Provider API key |
| `LLM_BASE_URL` | Yes (if using generic adapter) | Provider endpoint |
| `LLM_MODEL` | Yes (if using generic adapter) | Model identifier |
| `FLIGHTS_CSV` | No | Path to flights CSV (default: `flights_intl_v2.csv`) |
| `HOTELS_CSV` | No | Path to hotels CSV (default: `accommodation_intl_v2.csv`) |
| `ACTIVITIES_CSV` | No | Path to activities CSV (default: `activities_intl_v2.csv`) |

---

## Common failure modes and fixes

| Symptom | Cause | Fix |
|---|---|---|
| LLM returns markdown fences around JSON | Some models ignore "no fences" instruction | `parse_llm_response()` strips `` ```json `` automatically — verify it's called |
| `validation.errors` has "No flights selected" | No flights match the exact origin→dest+cabin filter | Broaden cabin filter; fall back to Economy if preferred class has no seats |
| `days` array length < `duration_days` | LLM ran out of tokens or context | Reduce `MAX_ACTIVITIES` from 6 to 4; split multi-city trips into separate prompts |
| Budget total mismatch > $10 | LLM arithmetic error | `validate_itinerary()` auto-corrects this — check the warning message |
| Destination not recognised | Alias missing from `CITY_ALIASES` | Add the alias; log unrecognised destinations for product feedback |
| Gemini returns empty `candidates` | Prompt flagged by safety filters | Check for ambiguous content; rephrase the system prompt to be more neutral |
| Activity IDs not in inventory | LLM hallucinated IDs despite instruction | Add ID verification loop to `validate_itinerary()`: cross-check all returned IDs against the inventory passed in the prompt |

---

## Code conventions

- **Function naming:** `verb_noun()` — e.g. `parse_user_request`, `query_inventory`, `build_ai_prompt`, `call_llm`, `validate_itinerary`
- **LLM call function:** always named `call_llm(system_prompt, user_prompt) -> str` regardless of provider
- **ID formats:** flights `INT-FL-NNNNN`, hotels `INT-HT-NNNNN`, activities `INT-AC-NNNNN`
- **Currency:** all prices in AUD; field names always include `_aud` suffix
- **Dates:** always `YYYY-MM-DD`; datetimes always `YYYY-MM-DD HH:MM`
- **No external API calls in Steps 1–3 or Step 5** — only Step 4 makes a network call
- **Keep `SYSTEM_PROMPT` as a module-level constant** — never build it dynamically
- **The `description` field is always markdown** — use `##` headers for each day

---

## Quick-start (Gemini Flash 2.5)

```bash
# 1. Install dependencies
pip install pandas google-generativeai python-dotenv

# 2. Set your free API key
echo "GEMINI_API_KEY=your-key-here" > .env

# 3. Generate mock data
python mock_fc.py

# 4. In itinerary_engine.py, replace call_claude() with call_llm() (see Gemini section above)

# 5. Run a test
python itinerary_engine.py "5 days Japan cherry blossom trip for 2 people"

# Output: itinerary_output.json
```

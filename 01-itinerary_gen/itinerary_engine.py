"""
itinerary_engine.py — AI Itinerary Builder Backend
====================================================
Flow:
  1. parse_user_request()   — Extract structured params from natural language
  2. query_inventory()      — Filter CSVs based on parsed params
  3. build_ai_prompt()      — Compose system + user prompt with inventory context
  4. call_llm()             — Call LLM API → get structured JSON itinerary
  5. validate_itinerary()   — Validate the returned JSON structure
  6. generate_itinerary()   — Orchestrates all steps; returns final JSON

Output JSON schema (itinerary_schema):
  {
    "meta": { trip_id, created_at, version },
    "trip": { title, destination_cities[], duration_days, theme, travel_dates,
              total_cost_aud, currency, group_size, status },
    "description": "Human-readable markdown itinerary...",
    "flights": [ { flight_id, airline, origin, destination, departure_datetime,
                   arrival_datetime, cabin_class, price_aud, seats_available,
                   booking_class, stops, baggage_kg, refundable, leg } ],
    "accommodation": [ { hotel_id, hotel_name, city, star_rating, room_type,
                         price_per_night_aud, nights, total_price_aud,
                         check_in, check_out, amenities, breakfast_included,
                         cancellation_policy } ],
    "days": [ { day_number, date, city, title, description,
                activities: [ { activity_id, activity_name, category, start_time,
                                duration_hours, price_aud, rating, notes } ] } ],
    "budget_breakdown": { flights_aud, accommodation_aud, activities_aud,
                          estimated_meals_aud, estimated_transport_aud, total_aud },
    "validation": { is_valid, warnings[], errors[] }
  }
"""

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
from typing import Optional

import pandas as pd
import anthropic


def load_local_env(env_path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    path = Path(__file__).resolve().with_name(env_path)
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if "=" in stripped:
            key, value = stripped.split("=", 1)
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
        else:
            continue

        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()

# ── Constants ──────────────────────────────────────────────────────────────────
FLIGHTS_CSV       = "data/flights_intl_v2.csv"
HOTELS_CSV        = "data/accommodation_intl_v2.csv"
ACTIVITIES_CSV    = "data/activities_intl_v2.csv"
MODEL             = "gemini-2.5-flash"
LLM_TEMPERATURE   = 0.1
MAX_JSON_ATTEMPTS = 8
MAX_FLIGHTS       = 5      # options to send to AI per leg
MAX_HOTELS        = 4      # options per city
MAX_ACTIVITIES    = 6      # options per city per day
MIN_SEATS         = 1      # filter out fully booked flights

# ── Theme keyword mapping ──────────────────────────────────────────────────────
THEME_KEYWORDS = {
    "luxury":    ["luxury", "premium", "5-star", "five star", "high-end", "first class"],
    "budget":    ["budget", "cheap", "affordable", "backpacker", "low-cost"],
    "adventure": ["adventure", "hiking", "outdoor", "extreme", "trek", "diving"],
    "romance":   ["romance", "romantic", "honeymoon", "couples", "anniversary"],
    "culture":   ["culture", "history", "museum", "heritage", "art", "historic"],
    "food":      ["food", "culinary", "gastronomy", "eat", "cuisine", "foodie"],
    "family":    ["family", "kids", "children", "child-friendly"],
    "beach":     ["beach", "island", "coast", "sea", "ocean", "surf"],
    "seasonal":  ["cherry blossom", "sakura", "autumn leaves", "foliage", "festival",
                  "new year", "christmas", "carnival"],
}

CABIN_THEME_MAP = {
    "luxury": "First",
    "budget": "Economy",
    "romance": "Business",
}

STAR_THEME_MAP = {
    "luxury": 5,
    "budget": 3,
    "romance": 4,
}

# ── Step 1: Parse user request ─────────────────────────────────────────────────

def parse_user_request(user_input: str, origin_city: str = "Sydney") -> dict:
    """
    Extract structured parameters from a free-text request.
    Returns a params dict used throughout the pipeline.
    
    Example:
      "5 days Japan cherry blossom trip for 2 people, budget $5000 AUD"
      → { duration_days: 5, destinations: ["Tokyo"], theme: "seasonal",
          budget_aud: 5000, group_size: 2, origin: "Sydney", ... }
    """
    text = user_input.lower()

    # Duration
    duration_match = re.search(r'(\d+)\s*(?:day|night|week)', text)
    if duration_match:
        val = int(duration_match.group(1))
        duration_days = val * 7 if 'week' in text[duration_match.start():duration_match.start()+20] else val
    else:
        duration_days = 5

    # Budget
    budget_aud = None
    budget_match = re.search(r'budget\s*[:=\-]?\s*\$\s*([\d,]+)', text)
    if not budget_match:
        budget_match = re.search(r'budget\s*[:=\-]?\s*([\d,]+)\s*(?:aud|dollars?)', text)
    if not budget_match:
        budget_match = re.search(r'\$\s*([\d,]+)', text)
    if budget_match:
        budget_aud = int(budget_match.group(1).replace(',', ''))
    if budget_aud is None:
        fallback_budget = os.environ.get("TRIP_BUDGET_AUD")
        if fallback_budget and fallback_budget.isdigit():
            budget_aud = int(fallback_budget)
        elif "budget" in text and "aud" in text and re.search(r'\bbudget\b\s*aud\b', text):
            raise ValueError(
                "Trip budget is missing from the request. Your shell likely expanded '$8000' before Python saw it. "
                "Use single quotes, escape the dollar sign, or pass TRIP_BUDGET_AUD=8000. Example: "
                "python itinerary_engine.py '5 days Japan cherry blossom trip for 2 people, budget $8000 AUD'"
            )

    # Group size
    group_match = re.search(r'(\d+)\s*(?:people|person|travell?er|adult|pax)', text)
    group_size = int(group_match.group(1)) if group_match else 1

    # Theme detection
    detected_theme = "culture"  # default
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            detected_theme = theme
            break

    # Destination city mapping
    CITY_ALIASES = {
        "japan": ["Tokyo"],
        "tokyo": ["Tokyo"],
        "kyoto": ["Tokyo"],          # mapped to Tokyo as proxy in mock data
        "paris": ["Paris"],
        "france": ["Paris"],
        "dubai": ["Dubai"],
        "singapore": ["Singapore"],
        "london": ["London"],
        "uk": ["London"],
        "new york": ["New York"],
        "nyc": ["New York"],
        "usa": ["New York", "Los Angeles", "San Francisco"],
        "bali": ["Bangkok"],         # Bangkok as closest match in mock data
        "thailand": ["Bangkok"],
        "bangkok": ["Bangkok"],
        "rome": ["Rome"],
        "italy": ["Rome"],
        "barcelona": ["Barcelona"],
        "spain": ["Barcelona"],
        "berlin": ["Berlin"],
        "germany": ["Berlin"],
        "seoul": ["Seoul"],
        "korea": ["Seoul"],
        "amsterdam": ["Amsterdam"],
        "istanbul": ["Istanbul"],
        "hong kong": ["Hong Kong"],
        "cape town": ["Cape Town"],
        "south africa": ["Cape Town"],
        "zurich": ["Zurich"],
        "switzerland": ["Zurich"],
        "mumbai": ["Mumbai"],
        "india": ["Mumbai"],
        "toronto": ["Toronto"],
        "canada": ["Toronto"],
    }

    destinations = []
    for alias, cities in CITY_ALIASES.items():
        if alias in text:
            destinations.extend(cities)
    destinations = list(dict.fromkeys(destinations))  # deduplicate, preserve order
    if not destinations:
        destinations = ["Tokyo"]  # sensible fallback for demo

    # Cabin class preference
    cabin_class = CABIN_THEME_MAP.get(detected_theme, "Economy")
    if "business" in text:
        cabin_class = "Business"
    elif "first class" in text or "first-class" in text:
        cabin_class = "First"
    elif "economy" in text:
        cabin_class = "Economy"

    # Hotel star preference
    min_stars = STAR_THEME_MAP.get(detected_theme, 3)

    return {
        "raw_input":      user_input,
        "origin":         origin_city,
        "destinations":   destinations,
        "duration_days":  duration_days,
        "theme":          detected_theme,
        "budget_aud":     budget_aud,
        "group_size":     group_size,
        "cabin_class":    cabin_class,
        "min_stars":      min_stars,
        "travel_year":    2026,
    }


# ── Step 2: Query inventory ────────────────────────────────────────────────────

def query_inventory(params: dict) -> dict:
    """
    Filters CSV datasets based on parsed params.
    Returns a context dict with candidate flights, hotels, activities.
    """
    flights_df    = pd.read_csv(FLIGHTS_CSV)
    hotels_df     = pd.read_csv(HOTELS_CSV)
    activities_df = pd.read_csv(ACTIVITIES_CSV)

    origin       = params["origin"]
    destinations = params["destinations"]
    theme        = params["theme"]
    cabin        = params["cabin_class"]
    min_stars    = params["min_stars"]
    budget       = params.get("budget_aud")
    group_size   = params.get("group_size", 1)

    # ── Flights ──
    # Outbound: origin → first destination
    outbound = flights_df[
        (flights_df["origin"].str.lower() == origin.lower()) &
        (flights_df["destination"] == destinations[0]) &
        (flights_df["cabin_class"] == cabin) &
        (flights_df["seats_available"] >= max(MIN_SEATS, group_size))
    ].sort_values("price_aud").head(MAX_FLIGHTS)

    # Return: last destination → origin
    inbound = flights_df[
        (flights_df["origin"] == destinations[-1]) &
        (flights_df["destination"].str.lower() == origin.lower()) &
        (flights_df["cabin_class"] == cabin) &
        (flights_df["seats_available"] >= max(MIN_SEATS, group_size))
    ].sort_values("price_aud").head(MAX_FLIGHTS)

    # Inter-city legs (if multi-destination)
    inter_legs = []
    for i in range(len(destinations) - 1):
        leg = flights_df[
            (flights_df["origin"] == destinations[i]) &
            (flights_df["destination"] == destinations[i+1]) &
            (flights_df["seats_available"] >= max(MIN_SEATS, group_size))
        ].sort_values("price_aud").head(3)
        inter_legs.append({"from": destinations[i], "to": destinations[i+1],
                            "options": leg.to_dict(orient="records")})

    # ── Hotels ──
    hotel_options = {}
    for city in destinations:
        h = hotels_df[
            (hotels_df["city"] == city) &
            (hotels_df["star_rating"] >= min_stars) &
            (hotels_df["max_guests"] >= group_size)
        ]
        # Budget guard: filter hotels whose per-night cost is plausible
        if budget:
            per_night_limit = budget * 0.25  # hotels ≤ 25% of total budget per night
            h = h[h["price_per_night_aud"] <= per_night_limit]
        hotel_options[city] = h.sort_values(
            ["star_rating", "price_per_night_aud"], ascending=[False, True]
        ).head(MAX_HOTELS).to_dict(orient="records")

    # ── Activities ──
    activity_options = {}
    for city in destinations:
        a = activities_df[activities_df["city"] == city].copy()

        # Older generated CSVs may not include group capacity or theme tags.
        # Keep the filter resilient so itinerary generation still works.
        if "group_size_max" in a.columns:
            a = a[a["group_size_max"] >= group_size]

        if "theme_tags" in a.columns:
            theme_mask = a["theme_tags"].astype(str).str.contains(theme, na=False)
            themed = a[theme_mask].sort_values("rating", ascending=False).head(MAX_ACTIVITIES)
            other = a[~theme_mask].sort_values("rating", ascending=False).head(MAX_ACTIVITIES - len(themed))
            activity_options[city] = pd.concat([themed, other]).head(MAX_ACTIVITIES).to_dict(orient="records")
        else:
            activity_options[city] = a.sort_values("rating", ascending=False).head(MAX_ACTIVITIES).to_dict(orient="records")

    return {
        "outbound_flight_options": outbound.to_dict(orient="records"),
        "inbound_flight_options":  inbound.to_dict(orient="records"),
        "inter_city_legs":         inter_legs,
        "hotel_options":           hotel_options,
        "activity_options":        activity_options,
    }


# ── Step 3: Build AI prompt ────────────────────────────────────────────────────

SYSTEM_PROMPT = """
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
""".strip()

def build_ai_prompt(params: dict, inventory: dict) -> str:
    """Compose the user-turn prompt with structured inventory and instructions."""
    return f"""
USER REQUEST: "{params['raw_input']}"

PARSED PARAMETERS:
{json.dumps({k: v for k, v in params.items() if k != 'raw_input'}, indent=2)}

AVAILABLE INVENTORY (pre-filtered for this trip):

=== OUTBOUND FLIGHTS ({params['origin']} → {params['destinations'][0]}) ===
{json.dumps(inventory['outbound_flight_options'], indent=2)}

=== RETURN FLIGHTS ({params['destinations'][-1]} → {params['origin']}) ===
{json.dumps(inventory['inbound_flight_options'], indent=2)}

=== INTER-CITY FLIGHTS ===
{json.dumps(inventory['inter_city_legs'], indent=2)}

=== HOTELS ===
{json.dumps(inventory['hotel_options'], indent=2)}

=== ACTIVITIES ===
{json.dumps(inventory['activity_options'], indent=2)}

TASK:
Generate a complete itinerary JSON matching this EXACT schema:

{{
  "meta": {{
    "trip_id": "<uuid>",
    "created_at": "<ISO datetime>",
    "version": "1.0"
  }},
  "trip": {{
    "title": "<engaging trip title>",
    "destination_cities": ["<city1>", ...],
    "duration_days": <int>,
    "theme": "<theme>",
    "travel_dates": {{
      "depart_date": "<YYYY-MM-DD from chosen outbound flight>",
      "return_date": "<YYYY-MM-DD from chosen return flight>"
    }},
    "total_cost_aud": <float>,
    "currency": "AUD",
    "group_size": <int>,
    "status": "draft"
  }},
  "description": "<human-readable markdown itinerary — full day-by-day narrative>",
  "flights": [
    {{
      "flight_id": "<exact ID from inventory>",
      "leg": "outbound|return|inter-city",
      "airline": "<string>",
      "origin": "<string>",
      "destination": "<string>",
      "departure_datetime": "<string>",
      "arrival_datetime": "<string>",
      "cabin_class": "<string>",
      "price_aud": <float>,
      "seats_available": <int>,
      "booking_class": "<string>",
      "stops": <int>,
      "baggage_kg": <int>,
      "refundable": <bool>
    }}
  ],
  "accommodation": [
    {{
      "hotel_id": "<exact ID from inventory>",
      "hotel_name": "<string>",
      "city": "<string>",
      "star_rating": <int>,
      "room_type": "<string>",
      "price_per_night_aud": <float>,
      "nights": <int>,
      "total_price_aud": <float>,
      "check_in": "<YYYY-MM-DD>",
      "check_out": "<YYYY-MM-DD>",
      "amenities": "<string>",
      "breakfast_included": <bool>,
      "cancellation_policy": "<string>"
    }}
  ],
  "days": [
    {{
      "day_number": <int>,
      "date": "<YYYY-MM-DD>",
      "city": "<string>",
      "title": "<string — e.g. 'Arrival & Shibuya Exploration'>",
      "description": "<2-3 sentence narrative for this day>",
      "activities": [
        {{
          "activity_id": "<exact ID from inventory>",
          "activity_name": "<string>",
          "category": "<string>",
          "start_time": "<HH:MM>",
          "duration_hours": <int>,
          "price_aud": <float>,
          "rating": <float>,
          "notes": "<practical tip for this activity>"
        }}
      ]
    }}
  ],
  "budget_breakdown": {{
    "flights_aud": <float>,
    "accommodation_aud": <float>,
    "activities_aud": <float>,
    "estimated_meals_aud": <float>,
    "estimated_transport_aud": <float>,
    "total_aud": <float>
  }},
  "validation": {{
    "is_valid": <bool>,
    "warnings": ["<string>", ...],
    "errors": ["<string>", ...]
  }}
}}

Return ONLY the JSON. No markdown. No explanation.
""".strip()


# ── Step 4: Call LLM ───────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Send prompt to LLM and return the raw text response."""
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key:
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{MODEL}:generateContent?key={gemini_api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": LLM_TEMPERATURE,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }
        request = urlrequest.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API request failed: {exc.code} {error_body}") from exc

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Gemini API returned an empty response payload.")
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        if not text_parts:
            raise RuntimeError("Gemini API returned no text in response parts.")
        return "".join(text_parts)

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        client = anthropic.Anthropic(api_key=anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text

    raise RuntimeError(
        "No LLM API key configured. Set GEMINI_API_KEY for Gemini or ANTHROPIC_API_KEY for Anthropic."
    )


# ── Step 5: Parse & validate response ─────────────────────────────────────────

REQUIRED_KEYS = {"meta", "trip", "description", "flights", "accommodation", "days",
                 "budget_breakdown", "validation"}

def validate_itinerary(itinerary: dict) -> dict:
    """
    Post-process validation: checks structure, recalculates totals, flags issues.
    Adds/updates the validation block in-place.
    """
    warnings = list(itinerary.get("validation", {}).get("warnings", []))
    errors   = list(itinerary.get("validation", {}).get("errors", []))

    # Structure check
    missing = REQUIRED_KEYS - set(itinerary.keys())
    if missing:
        errors.append(f"Missing required sections: {missing}")

    # Flight count
    if not itinerary.get("flights"):
        errors.append("No flights selected — itinerary cannot be booked.")

    # Hotel check
    if not itinerary.get("accommodation"):
        errors.append("No accommodation selected.")

    # Day count
    days = itinerary.get("days", [])
    expected_days = itinerary.get("trip", {}).get("duration_days", 0)
    if len(days) != expected_days:
        warnings.append(f"Day count mismatch: {len(days)} days generated vs {expected_days} expected.")

    # Budget recalculation
    bb = itinerary.get("budget_breakdown", {})
    computed_total = (
        bb.get("flights_aud", 0) +
        bb.get("accommodation_aud", 0) +
        bb.get("activities_aud", 0) +
        bb.get("estimated_meals_aud", 0) +
        bb.get("estimated_transport_aud", 0)
    )
    if abs(computed_total - bb.get("total_aud", 0)) > 10:
        warnings.append(
            f"Budget total mismatch: declared {bb.get('total_aud')} AUD vs "
            f"computed {computed_total:.2f} AUD. Auto-correcting."
        )
        itinerary["budget_breakdown"]["total_aud"] = round(computed_total, 2)
        itinerary["trip"]["total_cost_aud"] = round(computed_total, 2)

    itinerary["validation"] = {
        "is_valid": len(errors) == 0,
        "warnings": warnings,
        "errors":   errors,
    }
    return itinerary


def parse_llm_response(raw: str) -> dict:
    """Extract JSON from LLM response, handling edge cases."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def build_fallback_itinerary(params: dict, inventory: dict, reason: str) -> dict:
    """Build a schema-valid draft itinerary without LLM output."""
    duration_days = max(1, int(params.get("duration_days", 1)))
    destinations = params.get("destinations") or ["Tokyo"]
    city = destinations[0]
    travel_year = int(params.get("travel_year", datetime.now().year))
    start_date = datetime(travel_year, 4, 1).date()

    flights = []
    outbound_options = inventory.get("outbound_flight_options", [])
    inbound_options = inventory.get("inbound_flight_options", [])
    if outbound_options:
        outbound = outbound_options[0]
        flights.append({**outbound, "leg": "outbound"})
        start_date = datetime.strptime(outbound["departure_datetime"], "%Y-%m-%d %H:%M").date()
    if inbound_options:
        inbound = inbound_options[0]
        flights.append({**inbound, "leg": "return"})

    hotels_in_city = inventory.get("hotel_options", {}).get(city, [])
    accommodation = []
    accommodation_total = 0.0
    if hotels_in_city:
        nights = max(1, duration_days - 1)
        hotel = hotels_in_city[0]
        total_price = round(float(hotel["price_per_night_aud"]) * nights, 2)
        accommodation_total = total_price
        accommodation.append({
            **hotel,
            "nights": nights,
            "total_price_aud": total_price,
            "check_in": str(start_date),
            "check_out": str(start_date + timedelta(days=nights)),
        })

    day_activities = inventory.get("activity_options", {}).get(city, [])
    days = []
    activities_total = 0.0
    for i in range(duration_days):
        day_date = start_date + timedelta(days=i)
        selected_activity = []
        if i < len(day_activities):
            activity = day_activities[i]
            selected_activity = [{
                "activity_id": activity["activity_id"],
                "activity_name": activity["activity_name"],
                "category": activity["category"],
                "start_time": "10:00",
                "duration_hours": int(activity["duration_hours"]),
                "price_aud": float(activity["price_aud"]),
                "rating": float(activity["rating"]),
                "notes": "Schedule and timings can be adjusted in draft mode.",
            }]
            activities_total += float(activity["price_aud"])

        days.append({
            "day_number": i + 1,
            "date": str(day_date),
            "city": city,
            "title": "Arrival & Orientation" if i == 0 else f"Tokyo Day {i + 1}",
            "description": "Draft day plan generated from available inventory while LLM output was unavailable.",
            "activities": selected_activity,
        })

    flights_total = sum(float(f.get("price_aud", 0)) for f in flights)
    meals_total = round(60.0 * params.get("group_size", 1) * duration_days, 2)
    transport_total = round(25.0 * duration_days, 2)
    total = round(flights_total + accommodation_total + activities_total + meals_total + transport_total, 2)

    return {
        "meta": {
            "trip_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "version": "1.0",
        },
        "trip": {
            "title": f"Draft {duration_days}-Day {city} Itinerary",
            "destination_cities": destinations,
            "duration_days": duration_days,
            "theme": params.get("theme", "culture"),
            "travel_dates": {
                "depart_date": str(start_date),
                "return_date": str(start_date + timedelta(days=duration_days - 1)),
            },
            "total_cost_aud": total,
            "currency": "AUD",
            "group_size": params.get("group_size", 1),
            "status": "draft",
        },
        "description": (
            f"Draft itinerary generated from current inventory because the LLM response was unavailable.\n\n"
            f"## Day 1\nArrival and check-in.\n\n"
            f"## Day 2+\nRefine activities and transport before confirmation."
        ),
        "flights": flights,
        "accommodation": accommodation,
        "days": days,
        "budget_breakdown": {
            "flights_aud": round(flights_total, 2),
            "accommodation_aud": round(accommodation_total, 2),
            "activities_aud": round(activities_total, 2),
            "estimated_meals_aud": meals_total,
            "estimated_transport_aud": transport_total,
            "total_aud": total,
        },
        "validation": {
            "is_valid": False,
            "warnings": [f"LLM fallback used: {reason}"],
            "errors": [],
        },
    }


def summarize_llm_error(error_text: str) -> str:
    """Keep LLM failure reasons concise and human-readable."""
    first_line = error_text.strip().splitlines()[0] if error_text else "Unknown LLM error."
    return first_line[:300]


# ── Step 6: Orchestrator ───────────────────────────────────────────────────────

def generate_itinerary(
    user_input: str,
    origin_city: str = "Sydney",
    verbose: bool = False
) -> dict:
    """
    Main entry point. Given a natural language request, returns a structured
    itinerary JSON ready to be sent to the itinerary builder frontend.

    Args:
        user_input:  Free-text trip request, e.g. "5 days Japan cherry blossom"
        origin_city: Departure city (from user profile or app config)
        verbose:     If True, prints pipeline steps

    Returns:
        dict: Complete itinerary JSON (see module docstring for schema)
    """
    if verbose:
        print(f"\n[1/5] Parsing request: '{user_input}'")
    params = parse_user_request(user_input, origin_city)
    if verbose:
        print(f"      → theme={params['theme']}, destinations={params['destinations']}, "
              f"days={params['duration_days']}, budget={params['budget_aud']}")

    if verbose:
        print("[2/5] Querying inventory...")
    inventory = query_inventory(params)
    if verbose:
        out_count = len(inventory["outbound_flight_options"])
        in_count  = len(inventory["inbound_flight_options"])
        print(f"      → {out_count} outbound flights, {in_count} return flights")
        for city, hotels in inventory["hotel_options"].items():
            print(f"      → {len(hotels)} hotels in {city}")
        for city, acts in inventory["activity_options"].items():
            print(f"      → {len(acts)} activities in {city}")

    if verbose:
        print("[3/5] Building AI prompt...")
    user_prompt = build_ai_prompt(params, inventory)
    print("      → Prompt built (truncated to 500 chars):")
    print(user_prompt[:500] + "\n      ...")

    if verbose:
        print("[4/5] Calling LLM API...")

    raw_response = ""
    itinerary = None
    llm_failure_reason = None
    parse_guidance = ""
    for attempt in range(1, MAX_JSON_ATTEMPTS + 1):
        try:
            raw_response = call_llm(SYSTEM_PROMPT, user_prompt + parse_guidance)
        except RuntimeError as exc:
            llm_failure_reason = summarize_llm_error(str(exc))
            if verbose:
                print(f"      → LLM request failed on attempt {attempt}: {llm_failure_reason}")
            break
        try:
            itinerary = parse_llm_response(raw_response)
            break
        except json.JSONDecodeError as exc:
            if attempt == MAX_JSON_ATTEMPTS:
                llm_failure_reason = f"invalid JSON after {attempt} attempts: {exc}"
                break
            if verbose:
                print(
                    f"      → Attempt {attempt} returned invalid JSON ({exc}); retrying..."
                )
            parse_guidance = (
                "\n\nIMPORTANT: Your previous response was invalid JSON. "
                "Return exactly one complete JSON object with no comments, no trailing commas, "
                "and no additional text."
            )

    if verbose:
        print("[5/5] Parsing and validating response...")
    if itinerary is None:
        itinerary = build_fallback_itinerary(
            params,
            inventory,
            llm_failure_reason or "LLM output could not be parsed.",
        )
    itinerary = validate_itinerary(itinerary)

    # Ensure meta.trip_id exists
    if not itinerary.get("meta", {}).get("trip_id"):
        itinerary.setdefault("meta", {})["trip_id"] = str(uuid.uuid4())

    if verbose:
        v = itinerary["validation"]
        print(f"      → valid={v['is_valid']}, "
              f"warnings={len(v['warnings'])}, errors={len(v['errors'])}")
        if v["warnings"]:
            for w in v["warnings"]:
                print(f"        ⚠ {w}")
        if v["errors"]:
            for e in v["errors"]:
                print(f"        ✗ {e}")

    return itinerary


# ── CLI usage ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    request = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
              "5 days Japan cherry blossom trip for 2 people, budget $8000 AUD"

    print(f"Generating itinerary for: '{request}'")
    result = generate_itinerary(request, origin_city="Sydney", verbose=True)

    output_file = f"itinerary_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nItinerary saved to {output_file}")
    print(f"Trip: {result['trip']['title']}")
    print(f"Total cost: AUD {result['trip']['total_cost_aud']:,.0f}")
    print(f"Valid: {result['validation']['is_valid']}")

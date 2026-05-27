# `itinerary_engine.py`
### Intelligent Itinerary Recommendation — Flight Centre Influencer Marketplace

---

## What This Does

`itinerary_engine.py` is the **core AI recommendation engine**. Given a free-text trip request from an influencer, it produces a complete, structured itinerary in JSON — including real flights, hotels, and activities from the Flight Centre inventory. Every item in the output is traceable to a verified record in the database. Nothing is invented.

---

## Databases Used

This module uses **three separate CSV datasets** stored in the `data/` folder.

### `data/flights_intl_v2.csv`
| Field | Description |
|---|---|
| `flight_id` | Unique identifier (e.g. `INT-FL-00042`) |
| `airline` | Carrier name (e.g. Qantas, Emirates) |
| `origin` / `destination` | City names |
| `departure_datetime` / `arrival_datetime` | Format: `YYYY-MM-DD HH:MM` |
| `cabin_class` | Economy / Business / First |
| `price_aud` | Price per person in AUD |
| `seats_available` | Remaining seats |
| `stops` / `duration_minutes` | Routing information |
| `booking_class` | Saver / Flex / Full |
| `baggage_kg` | Included baggage allowance |
| `refundable` | Boolean |

### `data/accommodation_intl_v2.csv`
| Field | Description |
|---|---|
| `hotel_id` | Unique identifier (e.g. `INT-HT-00018`) |
| `hotel_name` | Property name |
| `city` / `country` | Location |
| `star_rating` | 1–5 stars |
| `room_type` | Standard / Deluxe / Suite etc. |
| `price_per_night_aud` | Nightly rate in AUD |
| `amenities` | Comma-separated list |
| `breakfast_included` | Boolean |
| `cancellation_policy` | Policy description |

### `data/activities_intl_v2.csv`
| Field | Description |
|---|---|
| `activity_id` | Unique identifier (e.g. `INT-AC-00103`) |
| `activity_name` | Activity title |
| `city` / `country` | Location |
| `category` | Culture / Adventure / Food / Relaxation |
| `duration_hours` | Duration in hours |
| `price_aud` | Price per person in AUD |
| `rating` | 1.0–5.0 |
| `suitable_for` | Solo / Couple / Family / Group |

> **Note:** These three datasets are used **only by this module**. They are not shared with the feasibility validator or content generator.

---

## How It Works — 6-Step Pipeline

```
User input (free text)
     │
     ▼
1. parse_user_request()   Extract: destination, duration, theme, budget, group size
     │
     ▼
2. query_inventory()      Filter: flights, hotels, activities matching the request
     │
     ▼
3. build_ai_prompt()      Compose: system prompt + inventory context (verified data only)
     │
     ▼
4. call_llm()             Call: Gemini 2.5 Flash → returns structured JSON
     │
     ▼
5. validate_itinerary()   Check: required keys, budget arithmetic, flight/hotel presence
     │                    Retry up to 8 times on JSON parse failure
     ▼
6. generate_itinerary()   Return: complete itinerary JSON
```

If all LLM attempts fail, `build_fallback_itinerary()` constructs a schema-valid draft from raw inventory data — the user always receives a usable starting point.

---

## Output Format

The function returns a JSON object with this structure:

```json
{
  "meta":      { "trip_id", "created_at", "version" },
  "trip":      { "title", "destination_cities", "duration_days", "theme",
                 "travel_dates", "total_cost_aud", "group_size", "status" },
  "description": "Human-readable markdown itinerary...",
  "flights":   [ { "flight_id", "airline", "origin", "destination",
                   "departure_datetime", "arrival_datetime", "price_aud", ... } ],
  "accommodation": [ { "hotel_id", "hotel_name", "city", "star_rating",
                       "price_per_night_aud", "check_in", "check_out", ... } ],
  "days":      [ { "day_number", "date", "city", "activities": [ ... ] } ],
  "budget_breakdown": { "flights_aud", "accommodation_aud", "activities_aud",
                        "estimated_meals_aud", "total_aud" },
  "validation": { "is_valid", "warnings", "errors" }
}
```

---

## Configuration

Set environment variables (or add to `.env`):

```env
ANTHROPIC_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
```

The active LLM provider is set inside the file:

```python
MODEL = "gemini-2.5-flash"   # change to claude-sonnet-4-6 for Anthropic
```

---

## Quick Start

```python
from itinerary_engine import generate_itinerary

result = generate_itinerary("5 days Tokyo cherry blossom for 2 people, budget $6000 AUD")
print(result["trip"]["title"])
print(result["budget_breakdown"]["total_aud"])
```

---

## Hallucination Guard

The LLM **only receives inventory records that have been retrieved and filtered first**. It cannot suggest a hotel, flight, or activity that was not passed to it in the prompt. If no suitable records are found, the output will say so explicitly — it will not invent alternatives.

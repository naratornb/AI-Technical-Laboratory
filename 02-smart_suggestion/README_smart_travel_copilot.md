# `smart_travel_copilot_v2_refined.ipynb`
### Context-Aware Co-Pilot — Flight Centre Influencer Marketplace

---

## What This Does

The co-pilot is a **conversational AI assistant** that guides influencers through the package creation process step by step. Unlike the itinerary engine which produces a complete plan in one call, the co-pilot works turn by turn — it reads the session state (what has been built so far) and suggests the most logical next action.

---

## Databases Used

This notebook uses **three separate CSV datasets** — the same physical files as `itinerary_engine.py` but accessed independently.

### `activities_enriched_v2.csv` — 360 rows · 13 columns
| Field | Description |
|---|---|
| `activity_id` | Unique identifier |
| `activity_name` | Activity title |
| `city` / `country` | Location (25 cities, 22 countries) |
| `category` | Food / Culture / Adventure / Relaxation |
| `vibe` | Mood tags e.g. `Romantic; Bustling; Modern` |
| `best_season` | e.g. `Spring; Autumn` |
| `suitable_for` | Solo / Couple / Family / Group |
| `duration_hours` | Duration |
| `price_aud` | Price per person in AUD |
| `rating` | 1.0–5.0 |
| `description` | Rich text description |
| `address` | Physical address |

> **Why enriched?** The `vibe`, `best_season`, `suitable_for`, and `description` fields are unique to this dataset — they were added specifically to make BM25 retrieval more semantically accurate for natural-language queries.

### `hotels_data.csv`
Standard hotel inventory: hotel_id, hotel_name, city, country, star_rating, room_type, price_per_night_aud.

### `flights_data.csv`
Standard flight inventory: flight_id, airline, origin, destination, departure_datetime, arrival_datetime, cabin_class, price_aud, seats_available.

---

## How It Works — Three-Prompt Pipeline

Each user turn goes through this sequence:

```
User message (free text)
     │
     ▼
NLP Preprocessing
  · Tokenise, lemmatise, remove stopwords (NLTK)
  · Entity extraction: city, country, budget, travel style, category, vibe
  · Error pre-classification: HUMAN_INPUT_ERROR · DB_GAP_ERROR · DETAIL_REQUEST
     │
     ▼
BM25 Retrieval
  · Searches activities / hotels / flights depending on intent
  · Returns top-5 verified matching records
  · Country-level queries expand to all cities in that country
     │
     ▼
Three-Prompt LLM Call
  · Prompt 1 (DOC):      Retrieved records + session history + user intent
  · Prompt 2 (CRITERIA): Co-pilot role + Chain-of-Thought rules + hallucination guard
  · Prompt 3 (FORMAT):   Strict JSON output schema
     │
     ▼
Structured JSON Response
  · suggestions[]  — verified items with item_id, price, rating
  · next_action    — what the co-pilot recommends doing next
  · warnings[]     — budget risk, gap detection, seasonality
  · copilot_message — plain-language message for the UI
     │
     ▼
Session Memory Update
  · User profile inferred (style, budget, city)
  · Itinerary accumulated across turns
  · Query history retained
```

---

## Error Handling

| Error Type | When Triggered | Response |
|---|---|---|
| `HUMAN_INPUT_ERROR` | Gibberish, inappropriate content, single character | Friendly clarification prompt, no LLM call |
| `DB_GAP_ERROR` | Destination or category not in inventory | Transparent explanation, alternative suggestions from inventory only |
| `DETAIL_REQUEST` | User asks for booking links or external sites | Answered using Flight Centre inventory data only — no competitor references |

---

## Session State

The session object persists across all turns:

```python
session = {
    "turn":         int,           # current turn number
    "itinerary":    [ items ],     # items auto-added from recommendations
    "history":      [ messages ],  # last 4 turns used as context
    "user_profile": { style, budget, last_city },
    "feedback_log": [ { id, signal } ]   # rejected items tracked
}
```

---

## Quick Start

```python
session = create_session()

result = copilot_turn(session, "I want a food experience in Tokyo")
result = copilot_turn(session, "something adventurous next")
result = copilot_turn(session, "Japan")          # country-level query
result = copilot_turn(session, "cheap options")  # budget filter
```

---

## Commercial Policy

The co-pilot **never directs users to competitor platforms**. Any query requesting external booking links (Booking.com, TripAdvisor, Expedia, etc.) is handled by returning the best available information from the Flight Centre inventory directly.

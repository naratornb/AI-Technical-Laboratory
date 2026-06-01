# Marketplace Content Generator

Generates polished, first-person travel package listings for the Flight Centre Influencer Marketplace from structured itinerary data, with automated quality validation and retry logic.

## Overview

This system orchestrates a 3-step pipeline:

1. **Trip Context Builder** — Serialises a trip plan from `trip_plans_v2.csv` into a structured plain-text block (hotel, activities, vibe, season, estimated cost)
2. **LLM Copywriting Call** — Sends the context to the LLM with a marketplace copywriter persona; produces a 150–250 word first-person listing in one call
3. **Listing Validator** — Checks word count, scans for banned competitor references, and detects price leakage; retries up to 3 times with correction instructions appended to the prompt

No retrieval step is needed — the trip data is already structured in the CSV and passed directly to the model as context.

---

## Quick Start

### 1. Installation

```bash
cd 04-content_generation
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install jupyter anthropic google-generativeai pandas python-dotenv plotly matplotlib seaborn
```

### 2. Get an API Key

**Option A: Google Gemini (Recommended)**

1. Go to https://aistudio.google.com/app/apikey
2. Sign in with a Google account
3. Click **Create API key**
4. Copy the key

**Option B: Anthropic Claude (Optional)**

1. Go to https://console.anthropic.com/
2. Navigate to **API Keys**
3. Click **Create Key** and copy it

### 3. Set Environment

Create or update `.env` in the project root:

```
GEMINI_API_KEY=your_gemini_key_here
MODEL_NAME=gemini-2.5-flash
```

Or as a shell variable:

```bash
export GEMINI_API_KEY="your_gemini_key_here"
```

### 4. Open the Notebook and Run All Cells

```bash
jupyter notebook travel_story_generator_refined-2.ipynb
```

The notebook loads `trip_plans_v2.csv`, runs the 3-step generation pipeline against a selected `trip_id` (or destination city), and renders the generated listing alongside the source itinerary, word count, and validation results.

---

## Input Format

The notebook accepts a `trip_id` or destination city name referencing rows in `trip_plans_v2.csv`. Examples:

- `"TRIP-042"` — specific trip by ID
- `"Bali"` — picks a random Bali trip from the dataset
- `"Sydney"` — picks a random Sydney trip from the dataset

---

## Output Schema

```json
{
  "meta": {
    "id": "uuid-v4",
    "created_at": "ISO-8601 timestamp",
    "version": "1.0"
  },
  "listing": {
    "trip_id": "TRIP-042",
    "city": "Bali",
    "word_count": 187,
    "text": "Waking up in Seminyak to the sound of distant gamelan...",
    "retry_count": 0
  },
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  }
}
```

---

## Supported Listing Styles

| Category | Items |
|---|---|
| Default style | Marketplace Package Listing (150–250 words, first-person, evocative) |
| Tone | aspirational, warm, travel-journalist voice |
| Banned references | booking.com, tripadvisor, expedia, airbnb, klook, viator |
| Banned content | prices, AUD values, per-night costs, external URLs |

---

## File Structure

```
04-content_generation/
├── travel_story_generator_refined-2.ipynb  # Notebook implementing the pipeline
├── trip_plans_v2.csv                       # Flight Centre verified trip inventory (5,718 rows)
└── README_content_generator.md             # This file
```

---

## Environment Variables

| Variable | Required | Purpose | Example |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key | `AIza...` |
| `ANTHROPIC_API_KEY` | No | Fallback Claude key | `sk-ant-...` |
| `MODEL_NAME` | No | LLM model override | `gemini-2.5-flash` |

---

## LLM Provider Swapping

By default, the notebook uses **Gemini 2.5 Flash**. To use **Claude** instead, set `ANTHROPIC_API_KEY` in `.env`; the `call_llm()` cell checks for `GEMINI_API_KEY` first, then falls back to `ANTHROPIC_API_KEY` if present.

---

## Troubleshooting

**"Trip ID not found"**

Cause: The provided ID does not exist in `trip_plans_v2.csv`.

Fix: List available IDs from a notebook cell:

```python
import pandas as pd
print(pd.read_csv('trip_plans_v2.csv')['trip_id'].unique()[:50])
```

**"Listing failed validation after 3 retries"**

Cause: The model repeatedly produced output below 150 words or containing banned competitor names.

Fix: Confirm `MODEL_NAME` is set to a supported model, then re-run the cell. You can also pass a more specific note (e.g. "Write a full 200-word listing with vivid detail") into the generator call.

**"Word count out of range"**

Cause: Generated listing was shorter than 150 or longer than 250 words.

Fix: The validator automatically retries with the word count issue appended to the prompt. If all 3 retries fail, inspect the raw outputs printed by the notebook.

---

## Architecture Deep Dive

### Step 1: Trip Context Builder

`build_trip_context()` groups all rows from `trip_plans_v2.csv` matching the selected `trip_id`, then serialises them into a structured plain-text block: trip name, destination, vibe tags, best season, hotel (name, stars, room type), estimated total cost, and a day-by-day activity list with slot, category, duration, and the first 60 characters of each description.

### Step 2: Single LLM Call

`build_system_prompt()` assigns the LLM a marketplace copywriter persona with explicit rules: first person, Australian English, 150–250 words, specific activity names drawn from the context, no prices, no external platform references. The data is passed in the user prompt — no retrieval step is required.

### Step 3: Listing Validator

`validate_listing()` checks word count (150–250), scans for banned competitor names (booking.com, tripadvisor, expedia, airbnb, klook, viator), and detects price patterns (`AUD$`, `per night`, `cost`). Returns `(True, [])` on pass or `(False, [issue1, issue2])` on fail. The caller retries up to `max_retries=3`, appending the issue list to the prompt on each attempt.

---

## Performance Considerations

- **Context building**: < 50ms
- **LLM call**: 2–5 seconds (Gemini 2.5 Flash)
- **Validation**: < 5ms
- **Total per listing**: typically 3–6 seconds
- **Token usage**: ~800–1,500 tokens per call
- **Retry overhead**: each retry adds ~3–5 seconds; worst case ~18 seconds

---

## Future Enhancements

- [ ] Batch generation for all trips in `trip_plans_v2.csv`
- [ ] Accept pre-submission draft JSON from the React frontend builder before database write
- [ ] A/B variant generation: two listing options for the influencer to choose between
- [ ] Tone customisation per influencer brand profile

---

## License

This project is provided as-is for educational and commercial use.

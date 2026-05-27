# AI Itinerary Builder Co-pilot

Acts as a conversational co-pilot while an influencer builds a travel itinerary — suggesting verified activities, warning about conflicts in real time, and assembling the final package in a strict JSON schema ready for submission.

## Overview

This system orchestrates a 5-step pipeline:

1. **Intent Parsing** — Extracts destination, vibe, duration, season, and group type from the influencer's input keywords
2. **RAG Activity Retrieval** — Queries `trip_plans_v2.csv` for verified activities matching the destination and vibe; returns only items from the Flight Centre inventory
3. **Co-pilot Suggestion Loop** — Interactively proposes day-slot activities, detects scheduling conflicts, and accepts or adjusts based on influencer feedback
4. **Real-Time Feasibility Check** — Calls the feasibility validator on each day as it is completed; surfaces R1–R11 warnings inline before the influencer moves to the next day
5. **Package Assembly** — Serialises the confirmed itinerary into the strict `travel_packages_v1` schema and writes a submission-ready JSON file

The co-pilot never invents activities — every suggestion is pulled from verified Flight Centre inventory. Hallucination is structurally prevented by design.

---

## Quick Start

### 1. Installation

```bash
cd travel-ai
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install anthropic google-generativeai pandas numpy scikit-learn python-dotenv

# Optional: for Jupyter visualisations
pip install jupyter plotly matplotlib seaborn
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

### 4. Run the Feature

```bash
python itinerary_builder.py 'Bali relaxation 7 days couple spring'
```

Output: `package_draft_<timestamp>.json` with the complete itinerary in submission schema.

### 5. Visualise the Results (Optional)

```bash
jupyter notebook itinerary_builder.ipynb
```

Run all cells to generate a day-by-day timeline, map of activity locations, and feasibility score breakdown.

---

## Usage Examples

### Command Line

```bash
# Start a co-pilot session for a Bali couple trip
python itinerary_builder.py 'Bali relaxation 7 days couple spring'

# Adventure trip in New Zealand
python itinerary_builder.py 'New Zealand adventure hiking 10 days'

# Verbose mode (shows RAG retrieval steps and rule checks)
python itinerary_builder.py 'Tokyo cultural food 5 days' --verbose
```

### Python API

```python
from itinerary_builder import build_itinerary

result = build_itinerary(
    input='Bali relaxation 7 days couple spring',
    interactive=False,
    verbose=True
)

print(result['package']['trip_name'])
print(result['validation']['is_valid'])

import json
with open('output.json', 'w') as f:
    json.dump(result, f, indent=2)
```

### Jupyter Notebook

Open `itinerary_builder.ipynb` to:
- Step through the co-pilot loop day by day with interactive widgets
- View inline feasibility warnings as each day is completed
- Export the final package as a submission-ready JSON

---

## Input Format

The system accepts natural-language keyword strings describing the desired package. Examples:

- `"Bali relaxation 7 days couple spring"`
- `"Tokyo cultural food 5 days solo autumn"`
- `"New Zealand adventure hiking 10 days group summer"`

### Recognised Parameters

| Parameter | Examples | Detected by |
|---|---|---|
| Destination | `Bali`, `Tokyo`, `New Zealand` | NLP entity extraction |
| Vibe | `relaxation`, `adventure`, `cultural`, `food` | Keyword matching against vibe taxonomy |
| Duration | `7 days`, `10 nights`, `two weeks` | Regex + NLP |
| Group type | `couple`, `solo`, `family`, `group` | Keyword classification |
| Season | `spring`, `autumn`, `December` | Keyword + month mapping |

---

## Output Schema

```json
{
  "meta": {
    "id": "uuid-v4",
    "created_at": "ISO-8601 timestamp",
    "version": "1.0"
  },
  "package": {
    "package_id": "PKG-DRAFT-<timestamp>",
    "trip_name": "Bali Serenity Escape",
    "destination_city": "Bali",
    "country": "Indonesia",
    "vibe": ["relaxation", "wellness"],
    "best_season": ["Spring", "Summer"],
    "travel_month": "October",
    "total_days": 7,
    "group_size": 2,
    "hotel_name": "The Layar Villa",
    "hotel_stars": 5,
    "days_json": "[{...day 1...}, {...day 2...}]"
  },
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  }
}
```

---

## Supported Vibes / Configurations

| Category | Items |
|---|---|
| Relaxation | beach, wellness, resort, spa, sunset |
| Adventure | hiking, diving, trekking, extreme sports, safari |
| Cultural | food tour, history, arts, local markets, temples |
| Romance | couple, honeymoon, boutique, private dining |
| Family | kid-friendly, theme parks, light activities |

---

## File Structure

```
travel-ai/
├── itinerary_builder.py              # Core co-pilot backend
├── itinerary_builder.ipynb           # Jupyter visualisation notebook
├── .env                              # Environment variables
├── data/
│   ├── trip_plans_v2.csv            # Verified activity inventory (5,718 rows)
│   └── travel_packages_v1.csv       # Existing packages for reference
├── package_draft_<timestamp>.json   # Generated output (created on each run)
├── README.md                         # This file
└── .github/
    └── copilot-instructions.md       # Detailed specifications
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

By default, the system uses **Gemini 2.5 Flash**. To use **Claude** instead:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python itinerary_builder.py 'Bali relaxation 7 days'
```

The `call_llm()` function checks for `GEMINI_API_KEY` first, then falls back to `ANTHROPIC_API_KEY` if present.

---

## Troubleshooting

**"No activities found for destination"**

Cause: The destination keyword does not match any `destination_city` value in `trip_plans_v2.csv`.

Fix:
```bash
# List all supported destinations
python itinerary_builder.py --list-destinations
```

**"Feasibility warning not resolving after adjustment"**

Cause: The replacement activity still triggers the same rule (e.g. R3 operating hours conflict).

Fix:
```bash
# Request an alternative suggestion explicitly
python itinerary_builder.py 'Bali 7 days' --skip-slot "Day 2 Morning"
```

**"Output JSON schema validation failed"**

Cause: The assembled `days_json` field contains a structural error.

Fix:
1. Run with `--verbose` to identify which day caused the schema error
2. Check that all activity slots contain required fields: `slot`, `activity_name`, `duration_minutes`, `category`
3. Re-run the affected day segment with `--rebuild-day 2`

---

## Development & Testing

### Run Unit Tests

```python
from itinerary_builder import build_itinerary

result = build_itinerary('Bali relaxation 7 days couple spring', interactive=False)
print(result['package']['total_days'])  # Should print 7
```

### Regenerate Mock Data

```bash
python generate_mock_trips.py
```

### Enable Verbose Logging

```python
result = build_itinerary(
    'Tokyo cultural food 5 days',
    verbose=True
)
```

---

## Architecture Deep Dive

### Step 1: Intent Parsing

The raw keyword input is processed by an NLP module that extracts structured fields: destination city, vibe tags, duration in days, group type, and preferred season. Extracted entities are validated against the vibe taxonomy and destination list from `trip_plans_v2.csv` before the pipeline continues.

### Step 2: RAG Activity Retrieval

Verified activities are retrieved from `trip_plans_v2.csv` using a combination of exact-match filtering (destination city) and semantic similarity (vibe and category). Only activities from the Flight Centre inventory are surfaced — the model cannot introduce external or fabricated options.

### Step 3: Co-pilot Suggestion Loop

For each day and time slot (Morning / Afternoon / Evening), the co-pilot proposes an activity from the retrieved inventory and explains the recommendation. The influencer can accept, request an alternative, or skip the slot. Conversation history is maintained so the model understands what has already been placed in the itinerary.

### Step 4: Real-Time Feasibility Check

After each day is confirmed, the partial itinerary is passed to the feasibility validator (R1–R11). Any warnings are surfaced inline with a plain-English explanation and a suggested fix. The influencer can resolve warnings before moving to the next day, preventing a backlog of issues at submission time.

### Step 5: Package Assembly

Once all days are confirmed and validation passes, the itinerary is serialised into the `travel_packages_v1` schema. The `days_json` field is assembled as a structured JSON string, all required top-level fields are populated from the parsed intent, and the final payload is written to a timestamped draft file ready for submission.

---

## Performance Considerations

- **Intent parsing**: < 200ms
- **RAG retrieval (5,718 rows)**: < 100ms per slot
- **Co-pilot LLM call per slot**: 2–4 seconds (Gemini 2.5 Flash)
- **Feasibility check per day**: 3–7 seconds
- **Full 7-day build (non-interactive)**: ~2–3 minutes end-to-end
- **Token usage**: ~500–900 tokens per slot suggestion; ~10,000–15,000 tokens for a full 7-day build

---

## Future Enhancements

- [ ] Connect to React frontend: stream co-pilot suggestions directly into the itinerary builder UI
- [ ] Self-learning: log accepted vs rejected suggestions to fine-tune retrieval ranking over time
- [ ] Budget constraint mode: filter activity and hotel suggestions by influencer's specified cost ceiling
- [ ] Export to PDF: generate a formatted influencer brief from the completed package

---

## License

This project is provided as-is for educational and commercial use.

---

## Support & Feedback

For issues, questions, or feature requests, refer to `.github/copilot-instructions.md` for detailed specs and architecture documentation.

# Feasibility Validator

Checks a completed travel itinerary package against 11 logical rules and returns structured pass/fail results with actionable fix guidance before submission for admin approval.

## Overview

This system orchestrates a 4-step pipeline:

1. **Package Ingestion** — Loads a package record from `travel_packages_v1.csv` and deserialises the `days_json` itinerary
2. **Context Serialisation** — Formats the full package — slots, times, durations, locations, season, group size — into a structured LLM-readable block
3. **LLM Rule Reasoning** — Sends the context to the LLM with all 11 rules defined; the model reasons over logical consistency without any external database lookups
4. **Structured Error Output** — Returns a validated JSON array of rule violations, each with error code, severity, affected field, and a concrete fix action

Every rule is applied through LLM reasoning over the package data itself — no hard-coded lookup tables or external APIs are called during validation.

---

## Quick Start

### 1. Installation

```bash
cd 03-feasibility_validation
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
jupyter notebook feasibility_validator_v3_2-2.ipynb
```

The notebook loads `travel_packages_v1.csv`, runs the 4-step validation pipeline against a selected `package_id`, and renders rule pass/fail results, severity breakdown, and a per-day timeline view.

---

## Input Format

The notebook accepts a `package_id` string referencing a row in `travel_packages_v1.csv`. Examples:

- `"PKG-V-001"` — valid package, should pass all 11 rules
- `"PKG-ERR-03"` — deliberately seeded with a rule violation for testing
- `"PKG-ERR-07"` — season mismatch violation

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
    "package_id": "PKG-ERR-07",
    "trip_name": "Kyoto Autumn Cultural Tour",
    "destination_city": "Kyoto",
    "total_days": 5
  },
  "validation": {
    "is_valid": false,
    "warnings": ["R11 — season mismatch detected"],
    "errors": [],
    "violations": [
      {
        "error_code": "SEASON_MISMATCH",
        "rule": "R11 — Seasonality & Weather",
        "severity": "warning",
        "field": "travel_month",
        "field_value": "December",
        "affected_item": "PKG-ERR-07 — best_season: Spring; Summer",
        "message": "Travel month December falls in Winter but this trip is rated best in Spring and Summer.",
        "action": "Change travel month to a Spring or Summer month, or select a trip available in Winter."
      }
    ]
  }
}
```

---

## Supported Rules

| # | Category | Rule | Priority | Type |
|---|---|---|---|---|
| R1 | Time & Connection | Travel time between activities | High | Hard |
| R2 | Time & Connection | Arrival-to-first-activity buffer | High | Hard |
| R3 | Operating Hours | Activity open at scheduled slot | High | Hard |
| R4 | Operating Hours | Day-specific closure check | High | Hard |
| R5 | Schedule Density | Max 3 activities per day | High | Soft |
| R6 | Location & Route | Distance/travel efficiency between locations | High | Soft |
| R7 | Activity Compatibility | Overlapping time conflicts | High | Hard |
| R8 | Inventory & Availability | Group size vs activity suitability | Low | Soft |
| R9 | Content Quality | Missing activity description | Low | Soft |
| R10 | Location & Route | Daily travel range (too many distant regions) | Medium | Soft |
| R11 | Seasonality & Weather | Activity/trip season vs travel month | Medium | Soft |

---

## File Structure

```
03-feasibility_validation/
├── feasibility_validator_v3_2-2.ipynb     # Notebook implementing the pipeline
├── travel_packages_v1.csv                 # Package-level records with days_json
├── feasibility check - Sheet1.numbers     # Spreadsheet companion
└── README_feasibility_validator_2.md      # This file
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

**"Package ID not found"**

Cause: The provided ID does not exist in `travel_packages_v1.csv`.

Fix: Open the CSV and pick a valid `package_id`, or list them from a notebook cell:

```python
import pandas as pd
print(pd.read_csv('travel_packages_v1.csv')['package_id'].tolist())
```

**"LLM returned malformed JSON"**

Cause: Model output did not match the expected violations array schema.

Fix: The notebook automatically retries up to 3 times with schema correction prompts. If it persists, confirm `MODEL_NAME` is set to a supported model.

**"days_json parse error"**

Cause: The `days_json` field in `travel_packages_v1.csv` is malformed for this package.

Fix:
1. Open `travel_packages_v1.csv` and locate the row by `package_id`
2. Validate the `days_json` column value at a JSON linter (e.g. jsonlint.com)

---

## Architecture Deep Dive

### Step 1: Package Ingestion

The notebook reads `travel_packages_v1.csv` and filters to the target `package_id`. The `days_json` field — a JSON string serialising the full day-by-day itinerary — is parsed into a Python dict for downstream use.

### Step 2: Context Serialisation

The package data is formatted into a structured plain-text block: destination, vibe, best season, travel month, group size, hotel, and each day's activity list with slot labels, times, durations, categories, and addresses. This block becomes the LLM's sole data source — no external lookups are made.

### Step 3: LLM Rule Reasoning

The 11 rules are injected into the system prompt as a formal specification. The LLM reasons over the itinerary context to identify violations, assessing logical consistency between slot times, travel distances, season tags, operating hours, and group size — tasks that benefit from language model reasoning rather than hard-coded rules engines.

### Step 4: Structured Error Output

The LLM is instructed to return only a JSON array of violation objects. Each object follows a fixed schema (error_code, rule, severity, field, field_value, affected_item, message, action). The caller validates the schema and retries up to 3 times if malformed output is returned.

---

## Performance Considerations

- **Package ingestion**: < 20ms
- **Context serialisation**: < 10ms
- **LLM rule reasoning**: 3–7 seconds (Gemini 2.5 Flash)
- **Total pipeline**: typically 4–8 seconds
- **Token usage**: ~1,200–2,500 tokens per call (scales with itinerary length)

---

## Future Enhancements

- [ ] Batch validation mode: check all packages in `travel_packages_v1.csv` in one run
- [ ] Pre-submission hook: integrate with React frontend to validate before database write
- [ ] Rule weighting: allow admins to promote soft rules to hard for stricter markets
- [ ] Violation trend dashboard: track most common rule failures across all influencers

---

## License

This project is provided as-is for educational and commercial use.

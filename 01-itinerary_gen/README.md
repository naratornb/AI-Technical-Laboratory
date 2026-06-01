# AI Itinerary Builder

An AI-powered travel itinerary generator that accepts natural-language trip requests and returns fully structured, itinerary JSON presets with flights, hotels, activities, and day-by-day plans.

## Overview

This system orchestrates a **6-step pipeline**:

1. **Parse Request** — Extract structured parameters (destination, duration, theme, budget) from natural language
2. **Query Inventory** — Filter flights, hotels, activities from CSV-based inventory
3. **Build Prompt** — Compose LLM prompt with filtered inventory as context
4. **Call LLM** — Send to Claude or Gemini Flash 2.5 for JSON generation
5. **Validate** — Check structure, recalculate budgets, flag warnings/errors
6. **Return JSON** — Output ready-to-use itinerary preset

The AI's role is **curation, not invention** — it selects real records from filtered inventory and sequences them into a coherent day-by-day plan. No fake IDs, prices, or properties are ever fabricated.

## Quick Start

### 1. Installation

```bash
# Navigate to project directory
cd 01-itinerary_gen

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install pandas anthropic
```

### 2. Get an API Key

**Option A: Google Gemini Flash 2.5 (Recommended, Free)**
- Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
- Click "Create API Key" → "Create API Key in new project"
- Copy the key

**Option B: Anthropic Claude (Optional fallback)**
- Go to [https://console.anthropic.com/](https://console.anthropic.com/)
- Create an account and generate an API key

### 3. Set Environment

Create or update `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
MODEL_NAME=gemini-2.5-flash
```

Or set as shell environment variable:

```bash
export GEMINI_API_KEY="your_api_key_here"
```

### 4. Generate an Itinerary

```bash
# ⚠️ IMPORTANT: Use single quotes to prevent shell expansion of $
python itinerary_engine.py '5 days Japan cherry blossom trip for 2 people, budget $8000 AUD'
```

**Output:** `itinerary_output_*.json` with complete trip structure

## Usage Examples

### Command Line

```bash
# Culture-focused trip
python itinerary_engine.py '3 days Paris museum and art, 1 person, budget $3000'

# Adventure trip
python itinerary_engine.py '7 days Thailand hiking and diving, 4 people, budget $12000 AUD'

# Romantic getaway
python itinerary_engine.py 'Honeymoon in Bali for 5 days, 2 people, $6500 budget'

# Verbose mode (shows pipeline steps)
python itinerary_engine.py '5 days Tokyo food tour for 3 people, budget $7000' --verbose
```

### Python API

```python
from itinerary_engine import generate_itinerary

# Generate itinerary
result = generate_itinerary(
    user_input='5 days Japan cherry blossom trip for 2 people, budget $8000 AUD',
    origin_city='Sydney',
    verbose=True  # Print pipeline steps
)

# Access results
print(f"Trip: {result['trip']['title']}")
print(f"Cost: AUD {result['trip']['total_cost_aud']:,.0f}")
print(f"Valid: {result['validation']['is_valid']}")

# Export to JSON
import json
with open('my_itinerary.json', 'w') as f:
    json.dump(result, f, indent=2)
```

## Input Format

The system accepts **free-form natural language** requests. Examples:

```
"5 days Japan cherry blossom trip for 2 people, budget $8000 AUD"
"3 days luxury Paris getaway, 1 person, budget €3000"
"7 days adventure hiking in Thailand, 4 friends, $12000 budget"
"romantic honeymoon in Bali for 5 days, 2 people"
```

### Recognized Parameters

| Parameter | Examples | Detected by |
|-----------|----------|-------------|
| **Duration** | 3 days, 5-day trip, 1 week, 14 nights | Regex: `(\d+)\s*(?:day\|night\|week)` |
| **Budget** | $8000 AUD, €5000, budget $3000 | Regex: dollar/budget keyword + number |
| **Destination** | Japan, Paris, New York, Bali, Thailand | City alias mapping (20+ cities) |
| **Theme** | cherry blossom, luxury, adventure, culture, food, romance, family, beach | Keyword detection |
| **Group Size** | 2 people, 3 travelers, 1 person | Regex: `(\d+)\s*(?:people\|person\|travelers)` |

**⚠️ Shell Quoting Note:**

If your budget contains a dollar sign, use **single quotes** to prevent shell expansion:

```bash
# ✅ CORRECT
python itinerary_engine.py '5 days Japan, budget $8000 AUD'

# ❌ WRONG ($ gets expanded by shell)
python itinerary_engine.py "5 days Japan, budget $8000 AUD"

# ✅ ALSO CORRECT (escape the $)
python itinerary_engine.py "5 days Japan, budget \$8000 AUD"
```

If budget is missing, the script will raise a clear error:

```
ValueError: Trip budget is missing from the request. Your shell likely expanded '$8000' before Python saw it. 
Use single quotes, escape the dollar sign, or pass TRIP_BUDGET_AUD=8000.
```

## Output JSON Schema

All itineraries return this schema:

```json
{
  "meta": {
    "trip_id": "uuid-v4",
    "created_at": "2026-01-15T10:30:00Z",
    "version": "1.0"
  },
  "trip": {
    "title": "Enchanting 5-Day Cherry Blossom Journey Through Japan",
    "destination_cities": ["Tokyo"],
    "duration_days": 5,
    "theme": "seasonal",
    "travel_dates": {
      "depart_date": "2026-03-20",
      "return_date": "2026-03-25"
    },
    "total_cost_aud": 8240.50,
    "currency": "AUD",
    "group_size": 2,
    "status": "draft"
  },
  "description": "Markdown-formatted day-by-day narrative...",
  "flights": [
    {
      "flight_id": "INT-FL-00123",
      "leg": "outbound|return|inter-city",
      "airline": "Singapore Airlines",
      "origin": "Sydney",
      "destination": "Tokyo",
      "departure_datetime": "2026-03-20 14:30",
      "arrival_datetime": "2026-03-21 06:15",
      "cabin_class": "Economy",
      "price_aud": 1200.0,
      "seats_available": 5,
      "booking_class": "Saver",
      "stops": 0,
      "baggage_kg": 20,
      "refundable": false
    }
  ],
  "accommodation": [
    {
      "hotel_id": "INT-HT-00456",
      "hotel_name": "Shinjuku Prince Hotel",
      "city": "Tokyo",
      "star_rating": 4,
      "room_type": "Deluxe",
      "price_per_night_aud": 180.0,
      "nights": 4,
      "total_price_aud": 720.0,
      "check_in": "2026-03-21",
      "check_out": "2026-03-25",
      "amenities": "wifi,gym,restaurant,room service",
      "breakfast_included": false,
      "cancellation_policy": "Free"
    }
  ],
  "days": [
    {
      "day_number": 1,
      "date": "2026-03-21",
      "city": "Tokyo",
      "title": "Arrival & Shinjuku Exploration",
      "description": "Arrive in Tokyo, settle into your hotel, explore the vibrant streets of Shinjuku...",
      "activities": [
        {
          "activity_id": "INT-AC-00789",
          "activity_name": "Senso-ji Temple Visit",
          "category": "Culture",
          "start_time": "14:00",
          "duration_hours": 2,
          "price_aud": 0.0,
          "rating": 4.8,
          "notes": "Best visited in late afternoon to avoid crowds"
        }
      ]
    }
  ],
  "budget_breakdown": {
    "flights_aud": 2400.0,
    "accommodation_aud": 720.0,
    "activities_aud": 600.0,
    "estimated_meals_aud": 1200.0,
    "estimated_transport_aud": 320.5,
    "total_aud": 5240.5
  },
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  }
}
```

## Supported Destinations

The system covers 20 cities with pre-built inventory:

| Region | Cities |
|--------|--------|
| **Japan** | Tokyo |
| **Europe** | Paris, London, Berlin, Barcelona, Rome, Amsterdam, Zurich, Istanbul |
| **Middle East** | Dubai |
| **South Asia** | Mumbai |
| **Southeast Asia** | Bangkok, Singapore, Hong Kong |
| **North America** | New York, Los Angeles, San Francisco, Toronto |
| **Africa** | Cape Town |
| **South Korea** | Seoul |

### Destination Aliases

The parser recognizes common aliases:

```
japan, tokyo, kyoto → Tokyo
paris, france → Paris
bali, thailand, bangkok → Bangkok
usa → New York, Los Angeles, San Francisco
... (20+ mappings)
```

## Supported Themes

Each theme influences cabin class preference, hotel star rating, and activity selection:

| Theme | Cabin | Min Stars | Triggered by |
|-------|-------|-----------|--------------|
| **luxury** | First | 5 | luxury, premium, 5-star, high-end |
| **budget** | Economy | 3 | budget, cheap, affordable, backpacker |
| **adventure** | Economy | 3 | adventure, hiking, outdoor, trek, diving |
| **romance** | Business | 4 | romance, honeymoon, couples, anniversary |
| **culture** | Economy | 3 | culture, history, museum, heritage, art |
| **food** | Economy | 3 | food, culinary, gastronomy, eat, cuisine |
| **family** | Economy | 3 | family, kids, children |
| **beach** | Economy | 3 | beach, island, coast, sea, ocean |
| **seasonal** | Economy | 3 | cherry blossom, sakura, autumn leaves |

## File Structure

```
01-itinerary_gen/
├── itinerary_engine.py              # Core backend (595 lines)
├── .env                             # Environment variables (GEMINI_API_KEY)
├── data/
│   ├── flights_intl_v2.csv         # Flight inventory (2,500 records)
│   ├── accommodation_intl_v2.csv   # Hotel inventory (2,500 records)
│   └── activities_intl_v2.csv      # Activity inventory (2,500 records)
├── itinerary_output_*.json         # Generated output (created on each run)
├── README.md                        # This file
└── .github/
    └── copilot-instructions.md     # Detailed specifications
```

## Environment Variables

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | Yes (if using Gemini) | Google Gemini API key | `AIzaSyD...` |
| `ANTHROPIC_API_KEY` | No (fallback only) | Anthropic Claude API key | `sk-ant-...` |

The script auto-loads these from `.env` on import. No manual `os.environ[]` setup needed.

## LLM Provider Swapping

By default, the system uses **Gemini 2.5 Flash** (free tier via REST API). To use Claude instead:

### Using Claude (Anthropic)

```bash
# Set Anthropic key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run (will detect and use Anthropic as fallback)
python itinerary_engine.py '5 days Japan, budget $8000 AUD'
```

The `call_llm()` function checks for `GEMINI_API_KEY` first, then falls back to Anthropic SDK if present.

### Using Other Providers (Groq, Ollama, OpenRouter)

You can extend `call_llm()` to support OpenAI-compatible APIs. See `.github/copilot-instructions.md` for detailed examples.

## Troubleshooting

### "Could not resolve authentication method"

**Cause:** Neither `GEMINI_API_KEY` nor `ANTHROPIC_API_KEY` is set.

**Fix:**
```bash
# Option 1: Set as environment variable
export GEMINI_API_KEY="your_key_here"

# Option 2: Create .env file
echo 'GEMINI_API_KEY=your_key_here' > .env
```

### "Trip budget is missing from the request"

**Cause:** Shell expanded `$8000` as a variable (common in double quotes).

**Fix:**
```bash
# Use single quotes
python itinerary_engine.py '5 days Japan, budget $8000 AUD'

# Or escape the dollar sign
python itinerary_engine.py "5 days Japan, budget \$8000 AUD"
```

### "No outbound flights, inbound flights, or accommodation available"

**Cause:** Budget too low for selected theme, or destination not in inventory.

**Fix:**
- Increase budget
- Use supported destination (see Supported Destinations table)
- Try a different theme

### LLM returns validation errors

**Check:**
- `validation.errors` array in JSON output
- Common issues: no flights matched filters, budget too tight, mismatched day count
- The validation block auto-corrects budget totals; check `validation.warnings`

## Development & Testing

### Run Unit Tests

```python
# Test parse_user_request()
from itinerary_engine import parse_user_request

params = parse_user_request('5 days Japan, budget $8000 for 2 people')
print(params['budget_aud'])  # Should print 8000
print(params['group_size'])  # Should print 2
print(params['theme'])       # Should print 'seasonal'
```

### Enable Verbose Logging

```python
result = generate_itinerary(
    'your request here',
    origin_city='Sydney',
    verbose=True  # Prints pipeline steps
)
```

## Architecture Deep Dive

### Step 1: Parse User Request

Extracts structured parameters using regex and keyword mapping:
- Duration: regex on day/night/week keywords
- Budget: regex on `$NNNN` or `budget NNNN`
- Theme: keyword matching against theme_keywords dict
- Destination: alias mapping (japan → Tokyo, paris → Paris, etc.)
- Group size: regex on people/person/traveler keywords

### Step 2: Query Inventory

Filters CSV data into candidate sets:
- **Flights**: outbound (origin → first dest), return (last dest → origin), inter-city
- **Hotels**: filtered by city, star rating ≥ min_stars, capacity ≥ group_size, budget plausibility
- **Activities**: filtered by city, capacity ≥ group_size, theme-boosted sort (matching theme float to top)

Max 5 outbound + 5 return + 4 hotels + 6 activities per city = ~20 records total. Keeps token budget under 8K.

### Step 3: Build AI Prompt

Compose two-turn prompt:
- **System**: Fixed canonical prompt defining role, rules (no fake IDs, markdown format for description, budget constraints)
- **User**: Parsed params + filtered inventory JSON + task instructions + exact output schema

### Step 4: Call LLM

Send to Gemini (REST) or Claude (SDK):
- Temperature: 0.1 (deterministic)
- Max tokens: 4096
- Expects: Single JSON object, no code fences, no explanation

### Step 5: Validate Itinerary

Post-generation checks:
- Structure: all required keys present
- Flights/hotels: at least one selected
- Days: count equals duration_days
- Budget: recalculate total, flag if diff > $10, auto-correct
- IDs: should verify against inventory passed in prompt

### Step 6: Return JSON

Full itinerary JSON with validation block indicating is_valid, warnings, errors.

## Performance Considerations

- **Inventory Query**: O(n) pandas filtering; ~50ms for 2,500-record CSVs
- **LLM Call**: Network-bound; typically 2-5 seconds (Gemini), 3-8 seconds (Claude)
- **Total Pipeline**: ~5-10 seconds per request
- **Token Usage**: ~2K input tokens, ~1K output tokens (well under free tier limits)

## Future Enhancements

- [ ] Activity ID validation against passed inventory
- [ ] Multi-city trip optimization (travel time between cities)
- [ ] Dynamic theme detection by sentiment analysis
- [ ] Database backend (replace CSV)
- [ ] REST API endpoint (FastAPI/Flask wrapper)
- [ ] Real-time flight/hotel API integration
- [ ] PDF export from notebook
- [ ] User feedback loop for itinerary refinement

## License

This project is provided as-is for educational and commercial use.

## Support & Feedback

For issues, questions, or feature requests, refer to `.github/copilot-instructions.md` for detailed specs and architecture documentation.

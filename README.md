# AI-Technical-Laboratory

A collection of four AI-powered features prototyped for the Flight Centre Influencer Marketplace. Each subfolder is a self-contained experiment with its own README, data, and runnable artifact (Python script or Jupyter notebook).

## Features

| # | Folder | What it does | Runtime |
|---|--------|--------------|---------|
| 01 | [01-itinerary_gen](01-itinerary_gen/README.md) | Turns a natural-language trip request into a fully structured itinerary JSON (flights, hotels, activities, day-by-day plan) using a 6-step parse → query → prompt → LLM → validate → output pipeline. | Python CLI (`itinerary_engine.py`) |
| 02 | [02-smart_suggestion](02-smart_suggestion/README_smart_travel_copilot.md) | Conversational co-pilot that guides influencers through package creation turn by turn. Combines NLP preprocessing, BM25 retrieval, and a three-prompt LLM pipeline with session memory. | Jupyter notebook |
| 03 | [03-feasibility_validation](03-feasibility_validation/README_feasibility_validator_2.md) | Validates a completed itinerary package against 11 logical rules (timing, hours, season, density, route efficiency) and returns structured pass/fail results with fix guidance. | Jupyter notebook |
| 04 | [04-content_generation](04-content_generation/README_content_generator.md) | Generates polished, first-person marketplace listings (150–250 words) from structured trip data, with automated validation for word count, banned references, and price leakage. | Jupyter notebook |

## Common Setup

All four features use the same LLM provider pattern: **Gemini 2.5 Flash** by default (free tier), with optional fallback to **Anthropic Claude**.

```bash
# Per-feature virtual environment
cd <feature-folder>
python3 -m venv .venv
source .venv/bin/activate

# Shared dependencies (each README lists exact packages)
pip install pandas python-dotenv google-generativeai anthropic
```

Set `GEMINI_API_KEY` (and optionally `ANTHROPIC_API_KEY`) in a `.env` file inside the feature folder you want to run. See each feature's README for full instructions.

## Repository Layout

```
AI-Technical-Laboratory/
├── 01-itinerary_gen/          # Itinerary builder (Python CLI + inventory CSVs)
├── 02-smart_suggestion/       # Smart Travel Copilot notebook
├── 03-feasibility_validation/ # Feasibility Validator notebook
├── 04-content_generation/     # Marketplace Content Generator notebook
├── Mockdata/                  # Shared mock datasets
├── AI_Features_Diagrams.excalidraw
├── AI_Features_Explained.html
├── AI_Features_Explained.pptx
├── LICENSE
└── README.md                  # This file
```

## Design Principle

Across all four features: **the LLM curates, it does not invent.** Flights, hotels, activities, and packages always come from the inventory CSVs — the model selects and sequences real records rather than fabricating IDs, prices, or properties.

## License

See [LICENSE](LICENSE).

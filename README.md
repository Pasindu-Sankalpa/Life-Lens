# LifeLens

Educational life-insurance needs analysis. A self-hosted Qwen model interviews. A deterministic engine calculates. Curated notes, linked to Lincoln Financial's public pages, teach.

## Run

```bash
# GPU 0 — conversation model
./scripts/serve_llm.sh

# API, kept off the GPU
./scripts/run_api.sh

# Website
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:3000.

## Formula

Coverage need = income replacement + mortgage + other debt + education + other named needs + lifelong legacy goal.

Income replacement = annual income × replacement percent × years.

Protection gap = coverage need − work coverage − personal coverage − earmarked savings.

No inflation and no discount rate are applied. Ten years and 70% are labeled assumptions until the person replaces them. Education uses an entered amount or a labeled $100,000-per-child placeholder.

## Database

SQLite file `data/lifelens.db`.

- `sessions` — quick or guided interview
- `profiles` — one household per session, with a source for every field
- `dependents` — age and education goal
- `messages` — conversation, tool trace, and why-this-matters prompts
- `calculations` — every engine result
- `scenarios` — what-if and life-event previews
- `knowledge_chunks` — educational notes and optional embeddings
- `meta` — knowledge version

# ak-md2anki

Compile **structured Markdown** into [Anki](https://apps.ankiweb.net) decks —
terminology tables become vocab cards, `### Q:` + blockquote blocks become
Q&A cards — with optional AI enrichment via free OpenRouter models.

Two output sinks:

- **AnkiConnect** — live upsert into a running Anki desktop (no import dialog).
- **`.apkg`** — a portable file you import anywhere (Anki need not be running).

👉 **[Full User Guide (USER_GUIDE.md)](USER_GUIDE.md)** — setup from zero, every
CLI command with examples, AI enrichment setup, AnkiConnect step-by-step,
troubleshooting, and SRS tips.

> Deterministic parsing first: where your Markdown already has structure, it is
> parsed directly and for free. The LLM only *adds* example sentences and answer
> paraphrases — it never re-derives or invents your content.

## Why

If you keep a knowledge base in Markdown (business terms, client-call Q&A,
glossaries), you can turn the relevant folder into a study deck in seconds and
review it in Anki (FSRS scheduler, browser, stats) before a meeting — without
hand-formatting flashcards or re-typing anything.

## Install

```bash
git clone https://github.com/andrey-kamensky/ak-md2anki.git
cd ak-md2anki
uv sync --extra dev          # or: python -m pip install -e ".[dev]"
```

## Quickstart

```bash
# 1. Build the intermediate deck (cards.json). Works with no API key.
ak-md2anki build path/to/notes.md

# Point at a whole directory (recursive):
ak-md2anki build path/to/business/

# 2a. Push to a running Anki desktop (requires the AnkiConnect add-on, code 2055492157):
ak-md2anki sync

# 2b. …or export a portable .apkg instead:
ak-md2anki export --apkg out/business.apkg
```

### AI enrichment (optional)

Export your OpenRouter key, then build as normal. The tool generates 1–2 extra
example sentences per term and paraphrases each Q&A answer into variants.
Results are cached, so re-runs cost nothing for unchanged content.

```bash
set -a; source .env; set +a      # OPENROUTER_API_KEY=sk-or-...
ak-md2anki build path/to/notes.md
```

Without a key, decks are still built from the source's own example sentences.

## Supported Markdown

**Terminology tables** (3- or 4-column; headers auto-detected):

```md
### Pricing (pricing & payment)

| Term | What it means | Why it matters | Say it like |
|---|---|---|---|
| **retainer** | monthly prepayment | Stabilizes revenue. | "Maintenance runs on a monthly retainer." |
```

**Q&A blocks**:

```md
## A. About you & credibility

### Q: "Tell me a bit about your background."

> "I've spent the last several years building internal tools..."
```

An optional italic lead-in before the blockquote is kept as a sub-label:

```md
### Q: "Have you worked in our industry before?"

*Even if no:*

> "I've worked a lot with similar workflows..."
```

## Decks produced

| Deck | Note type | Fields |
|---|---|---|
| `Business::Vocab` | Business Vocab | Term · Meaning · Why · Example · AIExamples · SourceId |
| `Business::ClientQA` | Client Q&A | Section · Question · Answer · Variants · SourceId |

Deck names and the enrichment model are configurable via environment variables
(see `ak_md2anki/config.py`).

## Security

- No secrets are committed; `.env` is gitignored (`.env.example` is the template).
- This tool never sends your source content to an LLM **except** the terms and
  canonical answers needed for enrichment. You can disable enrichment entirely
  with `--no-enrich`.
- Your source Markdown stays where it is — it is read by path, never copied in.

## Development

```bash
pytest              # tests (no network — HTTP is mocked)
ruff check .        # lint
```

See `AGENTS.md` for repository rules and `PLAN.md` for the design.

## License

MIT © Andrey Kamensky

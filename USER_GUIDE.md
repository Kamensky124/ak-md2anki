# ak-md2anki — User Guide

A practical guide to compiling your Markdown knowledge base into Anki decks.
Covers setup, the supported Markdown formats, every CLI command, AI enrichment,
and the AnkiConnect workflow from zero to daily training.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [What Markdown gets parsed](#what-markdown-gets-parsed)
  - [Terminology tables → Vocab cards](#terminology-tables--vocab-cards)
  - [Q&A blocks → Client Q&A cards](#qa-blocks--client-qa-cards)
  - [What is ignored](#what-is-ignored)
  - [Headings → tags](#headings--tags)
- [CLI reference](#cli-reference)
  - [`build` — compile Markdown → cards.json](#build--compile-markdown--cardsjson)
  - [`sync` — push to Anki via AnkiConnect](#sync--push-to-anki-via-ankiconnect)
  - [`export` — create a portable .apkg file](#export--create-a-portable-apkg-file)
  - [`list` — inspect cards.json](#list--inspect-cardsjson)
- [AI enrichment via OpenRouter](#ai-enrichment-via-openrouter)
  - [Getting a key](#getting-a-key)
  - [How enrichment works](#how-enrichment-works)
  - [Caching](#caching)
  - [Rate limits](#rate-limits)
  - [Disabling enrichment](#disabling-enrichment)
- [AnkiConnect setup (step-by-step)](#ankiconnect-setup-step-by-step)
- [Daily workflow](#daily-workflow)
- [Configuration via environment variables](#configuration-via-environment-variables)
- [Troubleshooting](#troubleshooting)
- [Tips for effective spaced repetition](#tips-for-effective-spaced-repetition)

---

## Prerequisites

- **Python ≥ 3.10** with [uv](https://docs.astral.sh/uv/) or `pip`.
- **Anki Desktop** (install from [apps.ankiweb.net](https://apps.ankiweb.net)). On
  Fedora you can use the `.tar.gz` Linux build or `flatpak install flathub net.ankiweb.Anki`.
- **AnkiConnect add-on** — required only for the `sync` command. Not needed for
  `build` or `export --apkg`. Install code: **`2055492157`**.
  See [AnkiConnect setup](#ankiconnect-setup-step-by-step) for the exact
  configuration the add-on needs.
- **OpenRouter API key** (free) — optional, only for AI enrichment. Without one
  decks still build from the source's own example sentences. Get one at
  [openrouter.ai/keys](https://openrouter.ai/keys).

---

## Installation

```bash
git clone https://github.com/Kamensky124/ak-md2anki.git
cd ak-md2anki
uv sync --extra dev          # or: python3 -m pip install -e ".[dev]"
```

Verify it works:

```bash
ak-md2anki build tests/fixtures/ --no-enrich
# ✅ 7 cards (4 vocab, 3 qa, 0 enriched)
```

---

## What Markdown gets parsed

ak-md2anki's v1 **structured extractor** recognizes exactly two patterns.
Everything else in the file is ignored (prose, bullets, comments, images).
This keeps the output predictable and the extraction free (no LLM calls).

### Terminology tables → Vocab cards

A GFM (GitHub-Flavored Markdown) table whose **first header cell contains "Term"**.
Both 3-column and 4-column variants are auto-detected.

**3-column format** (Term / Meaning / Example):

```md
### Pricing (pricing & payment)

| Term | What it means | Say it like |
|---|---|---|
| **retainer** | monthly prepayment for reserved capacity | "Maintenance runs on a monthly retainer." |
| **scope creep** | uncontrolled feature growth | "Let's lock the scope to avoid scope creep." |
```

**4-column format** (Term / Meaning / Why / Example):

```md
### Legal & compliance (legal)

| Term | What it means | Why it matters | Say it like |
|---|---|---|---|
| **fixed-price** / **fixed bid** | flat fee for a defined scope | Predictable for the client. | "Small tasks are fixed-price." |
| **milestone payment** | payment tied to checkpoints | Aligns incentives. | "Payment is milestone-based: 30/40/30." |
```

Rules:

- **Bold** markers (`**term**`) are stripped from the Term field but preserved
  in the HTML-rendered Meaning/Why/Example cells.
- Slash-separated variants (`**fixed-price** / **fixed bid**`) stay together as
  one Term: `fixed-price / fixed bid`. The first variant is used for card
  identity (determines which card gets updated on re-import).
- Column headers are classified by keyword match. The tool looks for: *Term*,
  *Meaning* / *What it means* / *Смысл*, *Why it matters* / *Why*, *Example* /
  *Say it like* / *Как звучит*. Unknown headers fall back to positional layout
  (col 0 = Term, col 1 = Meaning, col 2 = Example, col 3 = Why).
- Each row becomes one Vocab card in the `Business::Vocab` deck.

### Q&A blocks → Client Q&A cards

A heading line `### Q: "question text"` immediately followed by a blockquote
answer (`> answer text`). The nearest preceding `##` heading becomes the
**Section** field.

```md
## A. About you & credibility

### Q: "Tell me a bit about your background."

> "I've spent the last several years building CRM systems and internal
> operational tools — the software a business runs on day to day."

### Q: "Have you worked in our industry before?"

*Even if no:*

> "I've worked a lot with CRM-type workflows, which is the same shape of
> problem regardless of the industry."
```

Rules:

- The question is taken from the text between the first pair of quotes
  (`"…"` / `"…"` / `“…”`) after `Q:`.
- An italic lead-in line (`*Even if no:*`) between the heading and the
  blockquote is preserved as part of the answer.
- A blockquote can span multiple lines — all contiguous `>` lines are joined.
- The block stops at the next heading, a non-quote non-blank line, or a new
  table.
- Each Q&A block becomes one card in the `Business::ClientQA` deck.

### What is ignored

- Free-form prose paragraphs.
- Bullet lists without a `### Q:` heading.
- Image links, inline HTML, code blocks.
- Headings that aren't `### Q:` (they still serve as section/tag context).

### Headings → tags

| Heading | Becomes tag |
|---|---|
| `## A. About you & credibility` | `a-about-you-credibility` |
| `### Процесс и взаимодействие (engagement)` | `engagement` (short parenthetical extracted) |
| `### Pricing (pricing & payment)` | `pricing-payment` |

The tool prefers a short ASCII parenthetical label when one is present (up to
3 words). Otherwise the heading text before any parenthesis or em-dash is
slugified. All cards also carry a tag for the source file stem.

---

## CLI reference

All commands work from the project root. The `--verbose` / `-v` flag is
available on every subcommand.

### `build` — compile Markdown → `cards.json`

```bash
ak-md2anki build <path> [options]
```

| Option | Default | Effect |
|---|---|---|
| `<path>` | *(required)* | A `.md` file or a directory (recursive `*.md` glob). |
| `--no-enrich` | off | Skip AI enrichment — cards use only source examples. |
| `--out PATH` | `cards.json` | Where to write the intermediate artifact. |

**Examples:**

```bash
# Single file:
ak-md2anki build ~/org/wiki/business/marketing/client-call-qa.md

# Whole directory (recursive):
ak-md2anki build ~/org/wiki/business/marketing/

# No enrichment (fastest, works offline):
ak-md2anki build ~/org/wiki/business/marketing/ --no-enrich
```

`cards.json` is the intermediate artifact. It is a versioned JSON file
(sorted by card id, stable across runs). You can inspect it with any text
editor or use `ak-md2anki list`.

### `sync` — push to Anki via AnkiConnect

**Requires Anki Desktop running with the AnkiConnect add-on installed and
configured.** See [AnkiConnect setup](#ankiconnect-setup-step-by-step) for
the exact configuration.

```bash
ak-md2anki sync [--in cards.json] [--deck NAME] [--dry-run]
```

| Option | Effect |
|---|---|
| `--in PATH` | Read cards from a specific `cards.json` file (default: `cards.json`). |
| `--deck NAME` | Sync only this deck (e.g. `Business::Vocab`). |
| `--dry-run` | Show how many cards would be added/updated without touching Anki. |

**The sync is an upsert**: if a card with the same stable identity already
exists in Anki, its fields are updated in-place — you never get duplicates.
Tags are set on first add but not overwritten on update (v1).

**Examples:**

```bash
# Preview before writing:
ak-md2anki sync --dry-run

# Full sync:
ak-md2anki sync

# Sync only the vocab deck:
ak-md2anki sync --deck 'Business::Vocab'
```

### `export` — create a portable `.apkg` file

**Does not require Anki to be running.** The `.apkg` file can be imported via
Anki's File → Import menu, shared with colleagues, or archived.

```bash
ak-md2anki export --apkg <FILE> [--in cards.json] [--deck NAME]
```

| Option | Effect |
|---|---|
| `--apkg PATH` | **(required)** Output `.apkg` path. Creates parent directories. |
| `--in PATH` | Read from this `cards.json` (default: `cards.json`). |
| `--deck NAME` | Export only this deck. |

Re-importing the same `.apkg` more than once **updates** existing notes (stable
guid derived from the card id) — no duplicates.

**Example:**

```bash
ak-md2anki export --apkg out/business.apkg
# ✅ exported 175 cards → out/business.apkg
```

### `list` — inspect `cards.json`

```bash
ak-md2anki list [--in cards.json] [--deck NAME]
```

Prints one line per card: type icon, enrichment status (✨ = enriched),
id, and the Term or Question field.

**Examples:**

```bash
ak-md2anki list
ak-md2anki list --deck 'Business::ClientQA'
```

---

## AI enrichment via OpenRouter

### Getting a key

1. Visit [openrouter.ai/keys](https://openrouter.ai/keys) and create a free account.
2. Generate a key, then expose it to the tool:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Or use your existing key from another project:

```bash
set -a; source ~/pets/md-agent/.env; set +a
```

### How enrichment works

The tool runs an extra pass **after** deterministic extraction. It sends batched
requests to an OpenRouter free model. Two kinds of enrichment happen:

| Card type | What the LLM adds | Field populated |
|---|---|---|
| Vocab | 2 extra example sentences using the term in a B2B/consulting context | `AIExamples` |
| Q&A | 2 alternative phrasings of the canonical answer | `Variants` |

**Guardrail:** the LLM never invents the answer. For Q&A, it only
paraphrases the original blockquote. For Vocab, it generates *additional*
sentences — the source's own "Say it like" example is always kept verbatim.

### Caching

Enrichment results are cached in `enrichment.cache.json`, keyed by card id.
When you re-run `build` on the same Markdown (unchanged content), every term
and question that was already enriched is loaded from cache — **zero API calls**.
Only new or modified terms need fresh LLM requests.

### Rate limits

Free OpenRouter models have daily caps and modest throughput. The tool
respects these by:

- Batching ~10 terms per request (fewer API calls).
- Sleeping between batches to stay at ≤5 requests/minute (configurable).
- Caching aggressively so repeat runs are free.

If the primary model fails, a fallback (`meta-llama/llama-3.3-70b-instruct:free`)
is tried once.

### Disabling enrichment

- Pass `--no-enrich` to `build`: the deck uses only the source's own example
  sentences and the canonical Q&A answers. This is fast, works entirely offline,
  and never sends anything to an external API.
- Or simply don't set `OPENROUTER_API_KEY` — the tool skips enrichment
  gracefully with a one-line notice.

---

## AnkiConnect setup (step-by-step)

1. **Open Anki Desktop.**

2. **Install the AnkiConnect add-on:**
   - Go to Tools → Add-ons → Get Add-ons…
   - Paste the code: **`2055492157`**
   - Click OK, then restart Anki when prompted.

3. **Configure AnkiConnect's allowed origins.**
   - Tools → Add-ons → select "AnkiConnect" → Config.
   - Replace the config JSON with:

   ```json
   {
       "apiKey": null,
       "apiLogPath": null,
       "webBindAddress": "127.0.0.1",
       "webBindPort": 8765,
       "webCorsOrigin": "http://localhost",
       "webCorsOriginList": [
           "http://localhost",
           "app://obsidian.md"
       ]
   }
   ```

   - Click OK, then **restart Anki once more** for the config to take effect.

4. **Verify connectivity** (optional, but recommended):

   ```bash
   curl -s http://127.0.0.1:8765 -d '{"action":"deckNames","version":6}' | python3 -m json.tool
   ```

   You should see a JSON list of your current decks.

5. **Sync for the first time:**

   ```bash
   ak-md2anki sync --dry-run     # preview
   ak-md2anki sync               # go
   ```

The tool auto-creates the two note types (`Business Vocab` / `Client Q&A`)
and their decks on the first `sync`. You don't need to set up anything in Anki
beforehand.

---

## Daily workflow

This is the loop the tool was designed for:

```bash
# 1. Write or update notes in your Markdown knowledge base.
vim ~/org/wiki/business/marketing/objections.md

# 2. Build the deck. Enrichment results are cached — fast re-runs.
ak-md2anki build ~/org/wiki/business/marketing/

# 3. Push to Anki.
ak-md2anki sync

# 4. Open Anki and review your due cards.
```

After a week, you might add a new file:

```bash
ak-md2anki build ~/org/wiki/business/marketing/   # picks up the new file
ak-md2anki sync                                     # adds new cards only
```

Cards for files you haven't touched are re-parsed (instant — deterministic) and
enrichment is cache-hit (zero API cost). Only actually new or modified terms
trigger fresh LLM calls.

For a headless or offline machine where Anki isn't running, swap step 3:

```bash
ak-md2anki build ~/org/wiki/business/marketing/
ak-md2anki export --apkg ~/Downloads/business.apkg
# then copy the .apkg to your Anki machine and File → Import
```

---

## Configuration via environment variables

All defaults live in `ak_md2anki/config.py`. Override any of them:

| Variable | Default | Effect |
|---|---|---|
| `OPENROUTER_API_KEY` | *(none)* | Enables AI enrichment. |
| `AK_MD2ANKI_MODEL` | `openai/gpt-oss-20b:free` | Primary enrichment model. |
| `AK_MD2ANKI_FALLBACK_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Fallback model. |
| `AK_MD2ANKI_RPM` | `5` | Max requests per minute. |
| `AK_MD2ANKI_BATCH` | `10` | Terms per LLM batch. |
| `AK_MD2ANKI_VOCAB_DECK` | `Business::Vocab` | Deck name for vocab cards. |
| `AK_MD2ANKI_QA_DECK` | `Business::ClientQA` | Deck name for Q&A cards. |
| `ANKI_CONNECT_URL` | `http://127.0.0.1:8765` | AnkiConnect endpoint. |

Example — override the model and deck name:

```bash
export AK_MD2ANKI_MODEL="google/gemini-2.5-flash:free"
export AK_MD2ANKI_VOCAB_DECK="English::Business::Vocab"
ak-md2anki build notes/ --enrich
```

---

## Troubleshooting

**"Cannot reach AnkiConnect at http://127.0.0.1:8765"**

Anki Desktop is not running, or the AnkiConnect add-on isn't installed/
configured. Go through [AnkiConnect setup](#ankiconnect-setup-step-by-step)
from step 1. The most common miss: forgetting to restart Anki after changing
the add-on config.

**No cards extracted from my file**

Check that your Markdown matches one of the two recognized patterns:
- A GFM table whose first header cell contains `Term`.
- A `### Q: "…"` heading followed by a `>` blockquote.

Run with `--verbose` (`-v`) to see per-file card counts. If a file produces 0
cards and you expected some, its structure doesn't match.

**Enrichment is slow and I keep hitting rate limits**

Reduce the batch size: `export AK_MD2ANKI_BATCH=5`. Or skip enrichment
altogether with `--no-enrich` — the source's own examples are always kept.

**I imported the same `.apkg` twice and now I have duplicates**

This should not happen — the tool uses stable GUIDs. If you *do* see
duplicates, the .apkg was built from a different machine or the card IDs
changed (e.g. file was renamed). To fix: delete the deck in Anki completely,
then re-import the fresh .apkg. Going forward, always use `sync` (AnkiConnect)
for the tightest deduplication.

**`sync` added cards but the deck appears empty**

Anki shows only *due* cards by default. Click the deck and press **"Study Now"**
— your new cards are there, waiting. You can also browse: press `B` in Anki to
open the card browser, filter by deck.

---

## Tips for effective spaced repetition

1. **Review every day.** Even 5–10 minutes daily beats a 2-hour binge once a
   week. The FSRS algorithm in Anki schedules reviews at the optimal intervals
   — skipping days throws the algorithm off.

2. **Rate honestly.** On each card, press:
   - **Again** if you genuinely didn't know it.
   - **Good** if you knew it with some effort.
   - **Easy** if it was instant/trivial.
   Don't press Good when you actually failed — you're training the scheduler,
   not passing a test.

3. **Delete cards that don't serve you.** If a term is obvious after three
   reviews, or a Q&A answer is no longer relevant (your positioning changed),
   delete it. More cards ≠ better training.

4. **Edit in the source, not in Anki.** The Markdown file is the canonical
   source. If you need to fix a definition or improve an example, edit the
   `.md`, then re-run `build` + `sync`. The tool updates the card in place.
   Editing inside Anki will be overwritten on the next sync.

5. **Limit new cards per day.** Anki's default is 20 new cards/day — that's a
   good starting point. Overloading yourself leads to review debt and
   abandonment. You can always set it higher in Deck Options → New cards/day.

6. **Use the browser.** Press `B` in Anki to search, filter by tag, suspend
   cards temporarily, or find that one term you half-remembered. The tags from
   your Markdown headings make this easy.

# AGENTS.md — ak-md2anki

Rules for humans and AI agents working in this repository.

## Project purpose

A small CLI that compiles **structured Markdown** (terminology tables and
`### Q:` / blockquote Q&A blocks) into [Anki](https://apps.ankiweb.net) decks,
with optional AI enrichment (extra example sentences, answer paraphrases) via
free OpenRouter models. Output sinks: **AnkiConnect** (live upsert) and
**`.apkg`** (portable file). See `PLAN.md` for the full design.

The deterministic structured extractor is the heart of v1. An LLM prose
extractor for unstructured Markdown is planned for v2 but **out of scope now**.

## THIS REPOSITORY IS PUBLIC

- This repo is published openly. **Clients, recruiters, and peers can see it.**
- Behave accordingly: clean code, clear commits, no secrets, no private data,
  no slop. Treat every commit as part of a public portfolio.

## Security — non-negotiable

- **Never commit secrets.** API keys, tokens, passwords, `.env` files are
  gitignored and must stay out. `.env.example` carries placeholders only.
- **Never commit personal/private source content.** The author's real knowledge
  base (negotiation notes, client Q&A, pricing) lives **outside** this repo and
  is passed as a CLI path at runtime. Only **sanitized, synthetic** sample data
  belongs in `tests/fixtures/` and `examples/`.
- **No absolute personal paths** in committed code or docs. Resolve paths from
  CLI args, env vars, or the cwd — never hardcode `/home/...`.
- **Dependencies:** keep the surface small. Current runtime deps are
  `genanki`, `markdown`, `requests`. Adding a dependency requires justification.
- Review diffs for accidental secret/PII leaks before pushing.

## Code standards

- **Python ≥ 3.10**, typed (`from __future__ import annotations` + type hints).
- **`ruff`** is the linter/formatter of record. `ruff check .` must be clean.
- **`pytest`** must pass. New parser/extractor logic needs a test with a
  fixture. Enrichment/sink code that needs network must be tested with
  monkeypatched/mocked HTTP (no live calls in CI/tests).
- Keep functions small and pure where possible. The extractor and SRS math stay
  deterministic and unit-testable.
- No `print()` in library code — use the CLI layer for user output; raise
  typed exceptions otherwise.

## Commit / PR hygiene

- Conventional-style subjects (`feat:`, `fix:`, `docs:`, `test:`, `chore:`,
  `refactor:`), imperative mood, <=72-char subject.
- One logical change per commit. Never mix features with reformatting.
- Branch off `main`; the history should read as a clean narrative.

## Architecture invariants (do not silently break)

1. **Deterministic extraction first.** Where Markdown has structure (tables,
   `### Q:` blocks), parse it directly — never ask an LLM to re-derive it.
   The LLM only **enriches** (extra examples, paraphrases), never replaces,
   structured content.
2. **Grounded enrichment.** For Q&A, the LLM only paraphrases the canonical
   answer from the source — it never invents the answer. No hallucinated
   business/medical/legal advice may enter a card.
3. **Stable identity.** Every card has a deterministic `id`
   (`<type>__<source-stem>__<hash>`). Both sinks use it to **update** existing
   notes, never duplicate. Changing id generation invalidates every deck —
   do it deliberately.
4. **Sink-agnostic.** Cards flow through a `cards.json` intermediate. The sink
   (AnkiConnect / apkg) is swappable. Don't couple extraction to a sink.
5. **Restraint over coverage.** Default to **one card per knowledge unit**.
   Multi-type generation is opt-in; never inflate daily review volume by default.

## CLI surface (v1)

```
ak-md2anki build  <path> [--no-enrich] [--out cards.json]
ak-md2anki sync   [--in cards.json] [--dry-run]
ak-md2anki export --apkg FILE [--in cards.json]
ak-md2anki list   [--in cards.json] [--deck NAME]
```

## Running locally

```bash
uv sync --extra dev                 # or: pip install -e ".[dev]"
pytest                              # tests
ruff check .                        # lint
ak-md2anki build tests/fixtures/sample_vocab.md --no-enrich
```

## Files of record

- `PLAN.md` — full design, tool-landscape evaluation, sequencing.
- `AGENTS.md` — this file (repo rules).
- `README.md` — public-facing usage.

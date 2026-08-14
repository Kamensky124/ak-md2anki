# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Security

- LLM-sourced content (enrichment examples/variants and prose-extracted fields)
  is now HTML-escaped before reaching Anki note fields, so untrusted model
  output cannot inject markup or `<script>` into cards.

### Fixed

- Duplicate card ids when `--prose` ran alongside structured content. The prose
  extractor now only runs when a file yields no structured cards — both
  extractors share the same id scheme, so running both emitted duplicates and
  broke the "one card per id" upsert invariant.
- `extract_prose` now respects the OpenRouter RPM cap between chunks (matching
  `enrich`). Previously it burst-called the API on multi-section documents and
  tripped rate limits with no backoff.
- `store.save` now collapses duplicate ids defensively (first occurrence wins),
  so the persistence layer guarantees one card per id regardless of extractor
  behavior or same-stem file collisions.
- `store.load` now skips malformed card entries (bad type enum, missing keys)
  with a warning instead of aborting the whole load with an uncaught
  `ValueError`.
- `enrich` de-duplicates its primary/fallback model logic via
  `_call_with_fallback`, and the Q&A path now uses the fallback model too
  (previously only vocab had a fallback).
- The Q&A blockquote parser now keeps continuation paragraphs that omit the
  `>` prefix, so multi-paragraph answers are no longer truncated at the first
  un-prefixed line.

### Changed

- `mypy` (with `types-Markdown`) added to dev dependencies with a
  `[tool.mypy]` config; the package now type-checks clean.

## [0.1.0]

Initial v1 release — structured Markdown → Anki compiler with optional OpenRouter
enrichment, AnkiConnect live upsert, and `.apkg` export. See git history.

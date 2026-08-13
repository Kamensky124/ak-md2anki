# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

## [0.1.0]

Initial v1 release — structured Markdown → Anki compiler with optional OpenRouter
enrichment, AnkiConnect live upsert, and `.apkg` export. See git history.

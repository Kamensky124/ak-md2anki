"""cards.json persistence — the sink-agnostic intermediate artifact."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ak_md2anki.models import Card

logger = logging.getLogger(__name__)


def load(path: str | Path) -> list[Card]:
    """Load cards from a JSON file. Returns [] if the file is absent/empty.

    Malformed individual entries (bad type enum, missing keys, etc.) are
    skipped with a warning rather than aborting the whole load.
    """
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    raw = data.get("cards", []) if isinstance(data, dict) else data
    cards: list[Card] = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        try:
            cards.append(Card.from_dict(d))
        except (KeyError, ValueError, TypeError):
            logger.warning("Skipping malformed card entry in %s (id=%r)", p, d.get("id"))
    return cards


def save(path: str | Path, cards: list[Card]) -> None:
    """Write cards to JSON, sorted by id for stable diffs.

    Duplicate ids are collapsed (first occurrence wins) so the persistence
    layer enforces the "one card per id" invariant even if an extractor or a
    same-stem file collision emits duplicates.
    """
    seen: set[str] = set()
    unique: list[Card] = []
    for c in cards:
        if c.id in seen:
            continue
        seen.add(c.id)
        unique.append(c)
    payload = {
        "version": 1,
        "cards": [c.to_dict() for c in sorted(unique, key=lambda c: c.id)],
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

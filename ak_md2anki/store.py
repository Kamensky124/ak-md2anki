"""cards.json persistence — the sink-agnostic intermediate artifact."""

from __future__ import annotations

import json
from pathlib import Path

from ak_md2anki.models import Card


def load(path: str | Path) -> list[Card]:
    """Load cards from a JSON file. Returns [] if the file is absent/empty."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    raw = data.get("cards", []) if isinstance(data, dict) else data
    return [Card.from_dict(d) for d in raw if isinstance(d, dict)]


def save(path: str | Path, cards: list[Card]) -> None:
    """Write cards to JSON, sorted by id for stable diffs."""
    payload = {
        "version": 1,
        "cards": [c.to_dict() for c in sorted(cards, key=lambda c: c.id)],
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

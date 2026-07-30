"""Card data model — the unit that flows through extraction → store → sink."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CardType(str, Enum):
    VOCAB = "vocab"
    QA = "qa"


@dataclass
class Card:
    """A single flashcard.

    ``id`` is deterministic (``<type>__<source-stem>__<hash>``) and drives
    upsert in both sinks — never duplicate. ``source_hash`` is the hash of the
    source file content (used for incremental rebuilds / cache invalidation).
    """

    id: str
    deck: str
    type: CardType
    fields: dict[str, str]
    tags: list[str] = field(default_factory=list)
    source: str = ""
    source_locator: str = ""
    source_hash: str = ""
    enriched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "deck": self.deck,
            "type": self.type.value,
            "fields": self.fields,
            "tags": self.tags,
            "source": self.source,
            "source_locator": self.source_locator,
            "source_hash": self.source_hash,
            "enriched": self.enriched,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Card:
        return cls(
            id=d["id"],
            deck=d["deck"],
            type=CardType(d["type"]),
            fields=dict(d.get("fields", {})),
            tags=list(d.get("tags", [])),
            source=d.get("source", ""),
            source_locator=d.get("source_locator", ""),
            source_hash=d.get("source_hash", ""),
            enriched=bool(d.get("enriched", False)),
        )

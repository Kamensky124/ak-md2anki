""".apkg portable-file sink via genanki.

Produces a self-contained Anki package that can be imported via
File → Import in Anki Desktop. Re-importing updates existing notes (stable
guid derived from card.id).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

from ak_md2anki.card_templates import (
    FIELD_ORDER,
    QA_CSS,
    QA_MODEL_NAME,
    QA_TEMPLATE,
    VOCAB_CSS,
    VOCAB_MODEL_NAME,
    VOCAB_TEMPLATE,
)
from ak_md2anki.models import Card, CardType

# ----------- stable identifiers -----------

VOCAB_MODEL_ID = int(hashlib.sha1(b"ak-md2anki:vocab-model").hexdigest()[:8], 16)
QA_MODEL_ID = int(hashlib.sha1(b"ak-md2anki:qa-model").hexdigest()[:8], 16)


def _deck_id(deck_name: str) -> int:
    return int(hashlib.sha1(deck_name.encode()).hexdigest()[:8], 16)


_VOCAB_MODEL = genanki.Model(
    VOCAB_MODEL_ID,
    VOCAB_MODEL_NAME,
    fields=[{"name": f} for f in FIELD_ORDER[CardType.VOCAB]],
    templates=[
        {
            "name": VOCAB_TEMPLATE["Name"],
            "qfmt": VOCAB_TEMPLATE["Front"],
            "afmt": VOCAB_TEMPLATE["Back"],
        }
    ],
    css=VOCAB_CSS,
)

_QA_MODEL = genanki.Model(
    QA_MODEL_ID,
    QA_MODEL_NAME,
    fields=[{"name": f} for f in FIELD_ORDER[CardType.QA]],
    templates=[
        {
            "name": QA_TEMPLATE["Name"],
            "qfmt": QA_TEMPLATE["Front"],
            "afmt": QA_TEMPLATE["Back"],
        }
    ],
    css=QA_CSS,
)

_MODEL_MAP = {
    CardType.VOCAB: _VOCAB_MODEL,
    CardType.QA: _QA_MODEL,
}


def export_apkg(cards: list[Card], out_path: str | Path) -> None:
    """Write a ``.apkg`` file from cards, one deck per unique deck name."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    decks: dict[str, genanki.Deck] = {}
    for c in cards:
        dname = c.deck
        if dname not in decks:
            decks[dname] = genanki.Deck(_deck_id(dname), dname)
        model = _MODEL_MAP[c.type]
        order = FIELD_ORDER[c.type]
        fields = [c.fields.get(k, "") for k in order]
        # Write the stable id into the SourceId field for AnkiConnect search.
        fields[-1] = c.id
        note = genanki.Note(
            model=model,
            fields=fields,
            guid=genanki.guid_for(c.id),
            tags=c.tags,
        )
        decks[dname].add_note(note)

    pkg = genanki.Package(list(decks.values()))
    pkg.write_to_file(str(out))

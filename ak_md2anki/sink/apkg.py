""".apkg portable-file sink via genanki.

Produces a self-contained Anki package that can be imported via
File → Import in Anki Desktop. Re-importing updates existing notes (stable
guid derived from card.id).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

from ak_md2anki.models import Card, CardType

# ----------- stable identifiers -----------

VOCAB_MODEL_ID = int(hashlib.sha1(b"ak-md2anki:vocab-model").hexdigest()[:8], 16)
QA_MODEL_ID = int(hashlib.sha1(b"ak-md2anki:qa-model").hexdigest()[:8], 16)


def _deck_id(deck_name: str) -> int:
    return int(hashlib.sha1(deck_name.encode()).hexdigest()[:8], 16)


_VOCAB_MODEL = genanki.Model(
    VOCAB_MODEL_ID,
    "Business Vocab",
    fields=[
        {"name": "Term"},
        {"name": "Meaning"},
        {"name": "Why"},
        {"name": "Example"},
        {"name": "AIExamples"},
        {"name": "SourceId"},
    ],
    templates=[
        {
            "name": "Recall meaning",
            "qfmt": "{{Term}}",
            "afmt": (
                "{{FrontSide}}<hr id=answer>"
                '<div class="meaning">{{Meaning}}</div>'
                "{{#Why}}<p class='why'>💡 {{Why}}</p>{{/Why}}"
                "{{#Example}}<p class='example'>🗣 <i>{{Example}}</i></p>{{/Example}}"
                "{{#AIExamples}}<p class='ai'>🤖 {{AIExamples}}</p>{{/AIExamples}}"
            ),
        },
    ],
    css="""\
.meaning { font-size: 1.2em; margin-top: 0.5em; }
.why { color: #555; font-size: 0.9em; margin-top: 0.3em; }
.example, .ai { font-size: 0.85em; color: #333; margin-top: 0.2em; }""",
)

_QA_MODEL = genanki.Model(
    QA_MODEL_ID,
    "Client Q&A",
    fields=[
        {"name": "Section"},
        {"name": "Question"},
        {"name": "Answer"},
        {"name": "Variants"},
        {"name": "SourceId"},
    ],
    templates=[
        {
            "name": "Q&A",
            "qfmt": (
                "{{#Section}}<p class='section'>{{Section}}</p>{{/Section}}"
                "<div class='question'>{{Question}}</div>"
            ),
            "afmt": (
                "{{FrontSide}}<hr id=answer>"
                '<div class="answer">{{Answer}}</div>'
                "{{#Variants}}<p class='variants'>🔄 also: {{Variants}}</p>{{/Variants}}"
            ),
        },
    ],
    css="""\
.section { color: #888; font-size: 0.75em; margin-bottom: 0.2em; }
.question { font-size: 1.1em; font-weight: bold; }
.answer { margin-top: 0.5em; }
.variants { font-size: 0.85em; color: #555; margin-top: 0.5em; }""",
)

_MODEL_MAP = {
    CardType.VOCAB: _VOCAB_MODEL,
    CardType.QA: _QA_MODEL,
}

_FIELD_ORDER: dict[CardType, list[str]] = {
    CardType.VOCAB: ["Term", "Meaning", "Why", "Example", "AIExamples", "SourceId"],
    CardType.QA: ["Section", "Question", "Answer", "Variants", "SourceId"],
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
        order = _FIELD_ORDER[c.type]
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

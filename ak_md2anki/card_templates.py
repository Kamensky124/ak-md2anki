"""Shared Anki model definitions, templates, and field orders for sinks."""

from __future__ import annotations

from ak_md2anki.models import CardType

VOCAB_MODEL_NAME = "Business Vocab"
QA_MODEL_NAME = "Client Q&A"

VOCAB_FIELDS = ["Term", "Meaning", "Why", "Example", "AIExamples", "SourceId"]
QA_FIELDS = ["Section", "Question", "Answer", "Variants", "SourceId"]

FIELD_ORDER: dict[CardType, list[str]] = {
    CardType.VOCAB: VOCAB_FIELDS,
    CardType.QA: QA_FIELDS,
}

VOCAB_CSS = (
    ".meaning { font-size: 1.2em; margin-top: 0.5em; }\n"
    ".why { color: #555; font-size: 0.9em; margin-top: 0.3em; }\n"
    ".example, .ai { font-size: 0.85em; color: #333; margin-top: 0.2em; }"
)

QA_CSS = (
    ".section { color: #888; font-size: 0.75em; margin-bottom: 0.2em; }\n"
    ".question { font-size: 1.1em; font-weight: bold; }\n"
    ".answer { margin-top: 0.5em; }\n"
    ".variants { font-size: 0.85em; color: #555; margin-top: 0.5em; }"
)

VOCAB_TEMPLATE = {
    "Name": "Recall meaning",
    "Front": "{{Term}}",
    "Back": (
        "{{FrontSide}}<hr id=answer>"
        '<div class="meaning">{{Meaning}}</div>'
        "{{#Why}}<p class='why'>💡 {{Why}}</p>{{/Why}}"
        "{{#Example}}<p class='example'>🗣 <i>{{Example}}</i></p>{{/Example}}"
        "{{#AIExamples}}<p class='ai'>🤖 {{AIExamples}}</p>{{/AIExamples}}"
    ),
}

QA_TEMPLATE = {
    "Name": "Q&A",
    "Front": (
        "{{#Section}}<p class='section'>{{Section}}</p>{{/Section}}"
        "<div class='question'>{{Question}}</div>"
    ),
    "Back": (
        "{{FrontSide}}<hr id=answer>"
        '<div class="answer">{{Answer}}</div>'
        "{{#Variants}}<p class='variants'>🔄 also: {{Variants}}</p>{{/Variants}}"
    ),
}

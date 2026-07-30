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

VOCAB_CSS = """\
.card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #222; background-color: #fff; text-align: left; padding: 12px; }
.meaning { font-size: 1.25em; font-weight: 600; margin-top: 0.5em; color: #111; }
.why { color: #4a5568; font-size: 0.9em; margin-top: 0.4em; }
.example { font-size: 0.9em; color: #2d3748; margin-top: 0.4em; padding-left: 0.6em; border-left: 3px solid #3182ce; }
.ai-details { margin-top: 0.8em; font-size: 0.85em; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; background-color: #f7fafc; }
.ai-summary { font-weight: 600; color: #2b6cb0; cursor: pointer; outline: none; }
.ai { margin-top: 0.4em; color: #4a5568; line-height: 1.4; }

/* Dark mode support */
.nightMode .card, .night_mode .card { background-color: #1a202c; color: #e2e8f0; }
.nightMode .meaning, .night_mode .meaning { color: #f7fafc; }
.nightMode .why, .night_mode .why { color: #a0aec0; }
.nightMode .example, .night_mode .example { color: #cbd5e0; border-left-color: #63b3ed; }
.nightMode .ai-details, .night_mode .ai-details { border-color: #4a5568; background-color: #2d3748; }
.nightMode .ai-summary, .night_mode .ai-summary { color: #63b3ed; }
.nightMode .ai, .night_mode .ai { color: #cbd5e0; }
"""

QA_CSS = """\
.card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #222; background-color: #fff; text-align: left; padding: 12px; }
.section { color: #718096; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.3em; font-weight: 600; }
.question { font-size: 1.2em; font-weight: 700; color: #1a202c; }
.answer { margin-top: 0.6em; font-size: 1.05em; color: #2d3748; }
.variants-details { margin-top: 0.8em; font-size: 0.85em; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; background-color: #f7fafc; }
.variants-summary { font-weight: 600; color: #2b6cb0; cursor: pointer; outline: none; }
.variants { margin-top: 0.4em; color: #4a5568; line-height: 1.4; }

/* Dark mode support */
.nightMode .card, .night_mode .card { background-color: #1a202c; color: #e2e8f0; }
.nightMode .section, .night_mode .section { color: #a0aec0; }
.nightMode .question, .night_mode .question { color: #f7fafc; }
.nightMode .answer, .night_mode .answer { color: #cbd5e0; }
.nightMode .variants-details, .night_mode .variants-details { border-color: #4a5568; background-color: #2d3748; }
.nightMode .variants-summary, .night_mode .variants-summary { color: #63b3ed; }
.nightMode .variants, .night_mode .variants { color: #cbd5e0; }
"""

VOCAB_TEMPLATE = {
    "Name": "Recall meaning",
    "Front": "<div class='card'>{{Term}}</div>",
    "Back": (
        "<div class='card'>"
        "{{FrontSide}}<hr id=answer>"
        '<div class="meaning">{{Meaning}}</div>'
        "{{#Why}}<p class='why'>💡 {{Why}}</p>{{/Why}}"
        "{{#Example}}<p class='example'>🗣 <i>{{Example}}</i></p>{{/Example}}"
        "{{#AIExamples}}"
        "<details class='ai-details'><summary class='ai-summary'>🤖 AI Examples</summary><div class='ai'>{{AIExamples}}</div></details>"
        "{{/AIExamples}}"
        "</div>"
    ),
}

QA_TEMPLATE = {
    "Name": "Q&A",
    "Front": (
        "<div class='card'>"
        "{{#Section}}<p class='section'>{{Section}}</p>{{/Section}}"
        "<div class='question'>{{Question}}</div>"
        "</div>"
    ),
    "Back": (
        "<div class='card'>"
        "{{FrontSide}}<hr id=answer>"
        '<div class="answer">{{Answer}}</div>'
        "{{#Variants}}"
        "<details class='variants-details'><summary class='variants-summary'>🔄 Rephrasing / Variants</summary><div class='variants'>{{Variants}}</div></details>"
        "{{/Variants}}"
        "</div>"
    ),
}

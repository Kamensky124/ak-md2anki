"""AnkiConnect live-upsert sink (requires Anki desktop running + addon)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from ak_md2anki import config
from ak_md2anki.models import Card, CardType

logger = logging.getLogger(__name__)


# ── low-level AnkiConnect call ──────────────────────────────────────────────

def _invoke(action: str, **params: Any) -> Any:
    """Call AnkiConnect; raises on HTTP/result errors."""
    url = config.ANKI_CONNECT_URL
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.ConnectionError as err:
        raise RuntimeError(
            f"Cannot reach AnkiConnect at {url}. Is Anki running with the addon installed?"
        ) from err
    if isinstance(data, dict) and data.get("error") is not None:
        raise RuntimeError(f"AnkiConnect error ({action}): {data['error']}")
    return data.get("result")


def _multi(actions: list[dict]) -> list[Any]:
    """Batch multiple actions; returns list of results in the same order."""
    return _invoke("multi", actions=actions)


# ── deck & model setup ──────────────────────────────────────────────────────

_VOCAB_MODEL_DEF = {
    "modelName": "Business Vocab",
    "inOrderFields": [
        {"name": "Term"},
        {"name": "Meaning"},
        {"name": "Why"},
        {"name": "Example"},
        {"name": "AIExamples"},
        {"name": "SourceId"},
    ],
    "cardTemplates": [
        {
            "Name": "Recall meaning",
            "Front": "{{Term}}",
            "Back": (
                "{{FrontSide}}<hr id=answer>"
                '<div class="meaning">{{Meaning}}</div>'
                "{{#Why}}<p class='why'>💡 {{Why}}</p>{{/Why}}"
                "{{#Example}}<p class='example'>🗣 <i>{{Example}}</i></p>{{/Example}}"
                "{{#AIExamples}}<p class='ai'>🤖 {{AIExamples}}</p>{{/AIExamples}}"
            ),
        },
    ],
    "css": (
        ".meaning { font-size: 1.2em; margin-top: 0.5em; }"
        ".why { color: #555; font-size: 0.9em; margin-top: 0.3em; }"
        ".example, .ai { font-size: 0.85em; color: #333; margin-top: 0.2em; }"
    ),
}

_QA_MODEL_DEF = {
    "modelName": "Client Q&A",
    "inOrderFields": [
        {"name": "Section"},
        {"name": "Question"},
        {"name": "Answer"},
        {"name": "Variants"},
        {"name": "SourceId"},
    ],
    "cardTemplates": [
        {
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
        },
    ],
    "css": (
        ".section { color: #888; font-size: 0.75em; margin-bottom: 0.2em; }"
        ".question { font-size: 1.1em; font-weight: bold; }"
        ".answer { margin-top: 0.5em; }"
        ".variants { font-size: 0.85em; color: #555; margin-top: 0.5em; }"
    ),
}

_MODEL_DEFS = {CardType.VOCAB: _VOCAB_MODEL_DEF, CardType.QA: _QA_MODEL_DEF}

_FIELD_ORDER: dict[CardType, list[str]] = {
    CardType.VOCAB: ["Term", "Meaning", "Why", "Example", "AIExamples", "SourceId"],
    CardType.QA: ["Section", "Question", "Answer", "Variants", "SourceId"],
}


def _ensure_model(model_def: dict) -> None:
    name = model_def["modelName"]
    existing = _invoke("modelNames")
    if name in existing:
        return
    _invoke("createModel", **model_def)
    logger.info("Created Anki model '%s'", name)


def _ensure_deck(name: str) -> None:
    _invoke("createDeck", deck=name)


# ── sync ────────────────────────────────────────────────────────────────────

def sync_cards(cards: list[Card], dry_run: bool = False) -> dict[str, int]:
    """Upsert cards into Anki via AnkiConnect.

    Returns counts: ``{"added": N, "updated": N, "skipped": N}``.
    ``dry_run`` does a find-only pass — log what would change without writing.
    """
    # Ensure decks + models exist.
    used_decks: set[str] = {c.deck for c in cards}
    used_types: set[CardType] = {c.type for c in cards}
    for d in used_decks:
        _ensure_deck(d)
    for t in used_types:
        _ensure_model(_MODEL_DEFS[t])

    # Build a single combined findNotes query (OR of all SourceIds).
    # Note: Anki field search needs the field name followed by a colon and the
    # value. Special characters inside the value are fine since we use __
    # separators and alphanumeric hash tails.
    ids_list = [c.id for c in cards]
    # Anki search OR uses the syntax: (q1 OR q2 OR ...)
    query = "(" + " OR ".join(f'"SourceId:{uid}"' for uid in ids_list) + ")"
    found_ids = _invoke("findNotes", query=query)

    # Map SourceId → noteId.
    id_to_note: dict[str, int] = {}
    if found_ids:
        info = _invoke("notesInfo", notes=found_ids)
        for ni in info:
            source_id = ni.get("fields", {}).get("SourceId", {}).get("value", "").strip()
            if source_id:
                id_to_note[source_id] = ni.get("noteId")
            else:
                logger.warning("Note %s missing SourceId field", ni.get("noteId"))

    added, updated, skipped = 0, 0, 0
    multi_actions: list[dict] = []

    for c in cards:
        note_id = id_to_note.get(c.id)
        if note_id is not None:
            # Prepare updated fields. SourceId stays unchanged.
            fields = {}
            order = _FIELD_ORDER[c.type]
            for key in order:
                fields[key] = c.fields.get(key, "")
            fields["SourceId"] = c.id
            if dry_run:
                updated += 1
                continue
            multi_actions.append(
                {"action": "updateNoteFields", "params": {"note": {"id": note_id, "fields": fields}}}
            )
            updated += 1
        else:
            if dry_run:
                added += 1
                continue
            fields = {}
            order = _FIELD_ORDER[c.type]
            for key in order:
                fields[key] = c.fields.get(key, "")
            fields["SourceId"] = c.id
            multi_actions.append(
                {
                    "action": "addNote",
                    "params": {
                        "note": {
                            "deckName": c.deck,
                            "modelName": _MODEL_DEFS[c.type]["modelName"],
                            "fields": fields,
                            "tags": c.tags,
                        }
                    },
                }
            )
            added += 1

    if not dry_run and multi_actions:
        _multi(multi_actions)

    return {"added": added, "updated": updated, "skipped": skipped}

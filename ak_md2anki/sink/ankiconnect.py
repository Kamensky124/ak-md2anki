"""AnkiConnect live-upsert sink (requires Anki desktop running + addon)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from ak_md2anki import config
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
    "modelName": VOCAB_MODEL_NAME,
    "inOrderFields": [{"name": f} for f in FIELD_ORDER[CardType.VOCAB]],
    "cardTemplates": [VOCAB_TEMPLATE],
    "css": VOCAB_CSS,
}

_QA_MODEL_DEF = {
    "modelName": QA_MODEL_NAME,
    "inOrderFields": [{"name": f} for f in FIELD_ORDER[CardType.QA]],
    "cardTemplates": [QA_TEMPLATE],
    "css": QA_CSS,
}

_MODEL_DEFS = {CardType.VOCAB: _VOCAB_MODEL_DEF, CardType.QA: _QA_MODEL_DEF}


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
    if not cards:
        return {"added": 0, "updated": 0, "skipped": 0}

    # Ensure decks + models exist.
    used_decks: set[str] = {c.deck for c in cards}
    used_types: set[CardType] = {c.type for c in cards}
    for d in used_decks:
        _ensure_deck(d)
    for t in used_types:
        _ensure_model(_MODEL_DEFS[t])

    # Batched findNotes to avoid oversized search query strings.
    ids_list = [c.id for c in cards]
    found_ids: list[int] = []
    chunk_size = 100
    for i in range(0, len(ids_list), chunk_size):
        chunk = ids_list[i : i + chunk_size]
        query = "(" + " OR ".join(f'"SourceId:{uid}"' for uid in chunk) + ")"
        res = _invoke("findNotes", query=query)
        if res:
            found_ids.extend(res)

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
            order = FIELD_ORDER[c.type]
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
            order = FIELD_ORDER[c.type]
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

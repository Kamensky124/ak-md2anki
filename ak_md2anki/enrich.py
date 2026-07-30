"""LLM enrichment via free OpenRouter models (batched, cached).

Call-sites never block for more than one batch; ``sleep()`` is interleaved to
respect the RPM cap. All enrichment results are cached on disk so re-runs cost
zero API calls for unchanged terms / questions.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from pathlib import Path

import requests

from ak_md2anki import config
from ak_md2anki.models import Card, CardType

logger = logging.getLogger(__name__)

_HTML_TAGS = re.compile(r"<[^>]+>")

_VOCAB_PROMPT = """\
You are enriching B2B/consulting vocabulary for spaced-repetition study cards.

For each term below, write 2 short, natural example sentences a consultant
would say to a client in a business conversation (negotiation, discovery,
scoping, pricing, or delivery).

Return ONLY a JSON array — no preamble, no markdown:
[{"term":"<exact term>","examples":["<sentence 1>","<sentence 2>"]}]"""

_QA_PROMPT = """\
You are rephrasing client-call Q&A answers for a consultant's study deck.

For each question + canonical answer below, write 2 alternative ways to say
roughly the same thing — different phrasing, same meaning. Keep the tone
professional, conversational, 1-3 sentences each.

Return ONLY a JSON array — no preamble, no markdown:
[{"question":"<exact question>","variants":["<variant 1>","<variant 2>"]}]"""


def _api_key() -> str | None:
    return config.openrouter_key()


def _normalize_text(text: str) -> str:
    """Strip HTML tags and unescape entities, lowercased and trimmed for matching."""
    clean = _HTML_TAGS.sub("", text)
    clean = html.unescape(clean)
    return clean.strip().lower()


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to save enrichment cache: %s", e)


def _call_openrouter(messages: list[dict], model: str, retries: int = 2) -> dict | None:
    key = _api_key()
    if not key:
        return None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                config.OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as err:
            logger.warning(
                "OpenRouter call failed (attempt %d/%d): %s", attempt + 1, retries + 1, err
            )
            if attempt < retries:
                time.sleep(2**attempt)
    return None


def _extract_json(response: dict | None) -> list[dict] | None:
    if response is None:
        return None
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return None
    content = content.strip()
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1].strip()
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1:
        content = content[start : end + 1]
    try:
        res = json.loads(content)
        return res if isinstance(res, list) else None
    except json.JSONDecodeError:
        logger.debug("Could not parse JSON from LLM response: %s", content[:200])
        return None


def enrich(
    cards: list[Card],
    *,
    cache_path: str | Path | None = None,
    cache_enabled: bool = True,
) -> list[Card]:
    """Enrich vocab/QA cards via OpenRouter, returning updated cards.

    Cards already enriched or with cached results are left untouched.
    When ``OPENROUTER_API_KEY`` is absent the function is a no-op.
    """
    key = _api_key()
    if not key:
        logger.info("No OPENROUTER_API_KEY set — skipping enrichment")
        return cards

    c_path = Path(cache_path) if cache_path else Path("enrichment.cache.json")
    cache = _load_cache(c_path) if cache_enabled else {}
    cache_dirty = False
    vocab_terms = [c for c in cards if c.type == CardType.VOCAB]
    qa_cards = [c for c in cards if c.type == CardType.QA]

    # --- Vocab enrichment ---
    model = config.DEFAULT_MODEL
    batch_size = config.ENRICH_BATCH_SIZE
    vocab_needed: list[Card] = []
    for c in vocab_terms:
        cache_key = c.id
        if cache_enabled and cache_key in cache.get("vocab", {}):
            examples = cache["vocab"][cache_key]
            if isinstance(examples, list) and examples:
                c.fields["AIExamples"] = "<br>".join(examples)
                c.enriched = True
                continue
        vocab_needed.append(c)

    for batch_start in range(0, len(vocab_needed), batch_size):
        batch = vocab_needed[batch_start : batch_start + batch_size]
        terms = [c.fields.get("Term", "") for c in batch]
        messages: list[dict] = [
            {"role": "system", "content": _VOCAB_PROMPT},
            {"role": "user", "content": "\n".join(terms)},
        ]
        result = _call_openrouter(messages, model)
        parsed = _extract_json(result)
        if parsed is not None:
            for item in parsed:
                term = item.get("term", "")
                examples = list(item.get("examples", []) or [])
                if term and examples:
                    norm_term = _normalize_text(term)
                    for c in batch:
                        if _normalize_text(c.fields.get("Term", "")) == norm_term:
                            c.fields["AIExamples"] = "<br>".join(examples)
                            c.enriched = True
                            if cache_enabled:
                                cache.setdefault("vocab", {})[c.id] = examples
                                cache_dirty = True
                            break
        else:
            # Try fallback model once.
            logger.info("Trying fallback model %s", config.FALLBACK_MODEL)
            result = _call_openrouter(messages, config.FALLBACK_MODEL)
            parsed = _extract_json(result)
            if parsed is not None:
                for item in parsed:
                    term = item.get("term", "")
                    examples = list(item.get("examples", []) or [])
                    if term and examples:
                        norm_term = _normalize_text(term)
                        for c in batch:
                            if _normalize_text(c.fields.get("Term", "")) == norm_term:
                                c.fields["AIExamples"] = "<br>".join(examples)
                                c.enriched = True
                                if cache_enabled:
                                    cache.setdefault("vocab", {})[c.id] = examples
                                    cache_dirty = True
                                break

        if batch_start + batch_size < len(vocab_needed):
            time.sleep(60 / config.RPM_LIMIT)

    # --- QA enrichment ---
    qa_needed: list[Card] = []
    for c in qa_cards:
        cache_key = c.id
        if cache_enabled and cache_key in cache.get("qa", {}):
            variants = cache["qa"][cache_key]
            if isinstance(variants, list) and variants:
                c.fields["Variants"] = "<br>".join(variants)
                c.enriched = True
                continue
        qa_needed.append(c)

    for batch_start in range(0, len(qa_needed), batch_size):
        batch = qa_needed[batch_start : batch_start + batch_size]
        lines: list[str] = []
        for c in batch:
            q = c.fields.get("Question", "")
            a = c.fields.get("Answer", "")
            lines.append(f"Q: {q}\nA: {a}")
        messages = [
            {"role": "system", "content": _QA_PROMPT},
            {"role": "user", "content": "\n\n".join(lines)},
        ]
        result = _call_openrouter(messages, model)
        parsed = _extract_json(result)
        if parsed is not None:
            for item in parsed:
                question = item.get("question", "")
                variants = list(item.get("variants", []) or [])
                if question and variants:
                    norm_q = _normalize_text(question)
                    for c in batch:
                        if _normalize_text(c.fields.get("Question", "")) == norm_q:
                            c.fields["Variants"] = "<br>".join(variants)
                            c.enriched = True
                            if cache_enabled:
                                cache.setdefault("qa", {})[c.id] = variants
                                cache_dirty = True
                            break
        if batch_start + batch_size < len(qa_needed):
            time.sleep(60 / config.RPM_LIMIT)

    if cache_enabled and cache_dirty:
        _save_cache(c_path, cache)
    return cards

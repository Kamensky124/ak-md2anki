"""LLM prose extractor for unstructured Markdown (v2).

Extracts flashcards from raw prose Markdown notes when deterministic structures
(tables or `### Q:`) are absent. Respects embedded HTML comment hints:
- ``<!-- anki:skip -->``: Ignore the following block or section.
- ``<!-- anki:qa -->``: Prefer extracting Q&A cards from this section.
- ``<!-- anki:vocab -->``: Prefer extracting Vocab cards from this section.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path

from ak_md2anki import config
from ak_md2anki.enrich import _call_openrouter, _extract_json
from ak_md2anki.mdutil import heading_tag, md_to_html_block, md_to_html_inline, slugify
from ak_md2anki.models import Card, CardType

logger = logging.getLogger(__name__)

_PROSE_PROMPT = """\
You are an expert study flashcard extractor. Extract key knowledge units (vocabulary or Q&A)
from the provided markdown text into structured study cards.

Rules:
1. GROUNDED IN SOURCE ONLY: Do NOT invent facts, advice, or definitions not present in the text.
2. Restraint: Extract 1-3 high-value cards per section. Focus on essential concepts.
3. Card types:
   - "vocab": for terms, jargon, acronyms, or specific concepts.
   - "qa": for core questions, rules, principles, or procedural knowledge.

Return ONLY a JSON array — no preamble, no markdown formatting:
[
  {
    "type": "vocab",
    "term": "<exact term>",
    "meaning": "<explanation from text>",
    "why": "<context/reason if present or empty>",
    "example": "<example from text if present or empty>"
  },
  {
    "type": "qa",
    "section": "<heading/topic>",
    "question": "<concise question>",
    "answer": "<canonical answer from text>"
  }
]"""


def _stable_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _chunk_text(text: str) -> list[tuple[str, str]]:
    """Split markdown text into (section_title, chunk_content) pairs."""
    lines = text.splitlines()
    chunks: list[tuple[str, str]] = []
    current_section = ""
    current_lines: list[str] = []

    for line in lines:
        if line.strip() == "<!-- anki:skip -->":
            current_lines.append(line)
            continue

        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            if current_lines:
                chunks.append((current_section, "\n".join(current_lines)))
                current_lines = []
            if len(m.group(1)) <= 2:
                current_section = m.group(2).strip()
        current_lines.append(line)

    if current_lines:
        chunks.append((current_section, "\n".join(current_lines)))

    return [c for c in chunks if c[1].strip()]


def extract_prose(text: str, *, source: str = "") -> list[Card]:
    """Extract cards from unstructured prose Markdown text using LLM."""
    key = config.openrouter_key()
    if not key:
        logger.warning("No OPENROUTER_API_KEY set — cannot run prose extractor")
        return []

    source_stem = slugify(Path(source).stem) if source else "input"
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    base_tags = [source_stem, "prose"]

    chunks = _chunk_text(text)
    cards: list[Card] = []

    calls_made = 0
    for section, chunk in chunks:
        # Check skip hint
        if "<!-- anki:skip -->" in chunk:
            logger.info("Skipping section '%s' due to <!-- anki:skip --> hint", section)
            continue

        # Respect the OpenRouter RPM cap between API-calling chunks, mirroring
        # enrich(). Skipped chunks make no call and don't count.
        if calls_made > 0:
            time.sleep(60 / config.RPM_LIMIT)

        hint_prompt = ""
        if "<!-- anki:qa -->" in chunk:
            hint_prompt = "\nNote: Prefer extracting Q&A cards for this section."
        elif "<!-- anki:vocab -->" in chunk:
            hint_prompt = "\nNote: Prefer extracting Vocab cards for this section."

        messages = [
            {"role": "system", "content": _PROSE_PROMPT + hint_prompt},
            {"role": "user", "content": f"Section: {section}\n\n{chunk}"},
        ]

        resp = _call_openrouter(messages, config.DEFAULT_MODEL)
        parsed = _extract_json(resp)
        if parsed is None:
            resp = _call_openrouter(messages, config.FALLBACK_MODEL)
            parsed = _extract_json(resp)
        calls_made += 1

        if not parsed or not isinstance(parsed, list):
            continue

        for item in parsed:
            if not isinstance(item, dict):
                continue
            card_type = item.get("type", "").lower()

            if card_type == "vocab":
                term = item.get("term", "").strip()
                meaning = item.get("meaning", "").strip()
                why = item.get("why", "").strip()
                example = item.get("example", "").strip()
                if not term or not meaning:
                    continue

                card_id = f"vocab__{source_stem}__{_stable_hash(term.lower())}"
                tag = heading_tag(section) if section else ""
                tags = base_tags + ([tag] if tag else [])
                cards.append(
                    Card(
                        id=card_id,
                        deck=config.VOCAB_DECK,
                        type=CardType.VOCAB,
                        fields={
                            "Term": md_to_html_inline(term),
                            "Meaning": md_to_html_inline(meaning),
                            "Why": md_to_html_inline(why) if why else "",
                            "Example": md_to_html_inline(example) if example else "",
                            "AIExamples": "",
                            "SourceId": "",
                        },
                        tags=tags,
                        source=source,
                        source_locator=section or source_stem,
                        source_hash=source_hash,
                    )
                )
            elif card_type == "qa":
                question = item.get("question", "").strip()
                answer = item.get("answer", "").strip()
                sec = item.get("section", section).strip() or section
                if not question or not answer:
                    continue

                card_id = f"qa__{source_stem}__{_stable_hash(question.lower())}"
                tag = heading_tag(sec) if sec else ""
                tags = base_tags + ([tag] if tag else [])
                cards.append(
                    Card(
                        id=card_id,
                        deck=config.QA_DECK,
                        type=CardType.QA,
                        fields={
                            "Section": sec,
                            "Question": md_to_html_inline(question),
                            "Answer": md_to_html_block(answer),
                            "Variants": "",
                            "SourceId": "",
                        },
                        tags=tags,
                        source=source,
                        source_locator=sec or source_stem,
                        source_hash=source_hash,
                    )
                )

    return cards


def extract_prose_file(path: str | Path) -> list[Card]:
    """Extract cards from an unstructured Markdown file on disk."""
    p = Path(path)
    return extract_prose(p.read_text(encoding="utf-8"), source=str(p))

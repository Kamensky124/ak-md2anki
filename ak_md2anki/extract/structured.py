"""Deterministic structured extractor (zero LLM cost).

Recognizes two Markdown patterns:

* **Terminology tables** — a GFM table whose first header cell matches ``Term``.
  Columns are classified by header (Term / Meaning / Why / Example); 3- and
  4-column variants are both supported. Each row becomes a Vocab card.
* **Q&A blocks** — a ``### Q: "..."`` heading immediately followed by a
  blockquote answer (an optional ``*italic lead-in*`` line in between is kept
  as a sub-label). Each becomes a Q&A card; the current ``##`` heading is the
  Section.

Everything else in the file is ignored. This parser is intentionally strict so
the output is predictable and reviewable.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ak_md2anki import config
from ak_md2anki.mdutil import (
    heading_tag,
    md_to_html_block,
    md_to_html_inline,
    slugify,
    strip_emphasis,
)
from ak_md2anki.models import Card, CardType

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_Q_HEADING = re.compile(r"^#{1,6}\s+Q\s*:\s*(.+?)\s*$", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}.*$")
_LEADIN = re.compile(r"^\s*\*[^*\n]+\*\s*$")
_PAREN = re.compile(r"\(([^()]*)\)")

# Header → logical column role.
_TERM_HEADERS = ("term",)
_MEANING_HEADERS = ("meaning", "смысл", "what it means", "определение", "definition")
_WHY_HEADERS = ("why",)
_EXAMPLE_HEADERS = ("example", "say it like", "как звучит", "phrase", "пример")


def _stable_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _split_row(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [c.strip() for c in body.split("|")]


def _classify_columns(headers: list[str]) -> dict[str, int]:
    """Map header cells to roles. Falls back to positional layout."""
    roles: dict[str, int] = {}
    for idx, h in enumerate(headers):
        key = h.lower().strip()
        if any(t in key for t in _TERM_HEADERS) and "term" not in roles:
            roles["term"] = idx
        elif any(t == key or t in key for t in _MEANING_HEADERS) and "meaning" not in roles:
            roles["meaning"] = idx
        elif any(t in key for t in _WHY_HEADERS) and "why" not in roles:
            roles["why"] = idx
        elif any(t in key for t in _EXAMPLE_HEADERS) and "example" not in roles:
            roles["example"] = idx
    # Positional fallbacks for the common shapes.
    roles.setdefault("term", 0)
    if "meaning" not in roles:
        roles["meaning"] = min(1, len(headers) - 1)
    if "example" not in roles and len(headers) >= 3:
        roles["example"] = 2
    if "why" not in roles and len(headers) >= 4:
        roles["why"] = 3
    return roles


def _is_separator(line: str) -> bool:
    return bool(_TABLE_SEP.match(line)) and "-" in line


def _read_table(lines: list[str], start: int) -> tuple[list[str], int]:
    """Return (table_lines, next_index) starting from a header row."""
    j = start
    block: list[str] = []
    while j < len(lines) and _TABLE_ROW.match(lines[j]):
        block.append(lines[j])
        j += 1
    return block, j


def _parse_table(
    block: list[str],
    *,
    source_stem: str,
    source: str,
    source_hash: str,
    category_tag: str,
    base_tags: list[str],
) -> list[Card]:
    if len(block) < 2:  # need header + separator + >=1 row
        return []
    headers = _split_row(block[0])
    roles = _classify_columns(headers)
    cards: list[Card] = []
    for row_line in block[2:]:  # skip header + separator
        cells = _split_row(row_line)
        if not any(c.strip() for c in cells):
            continue

        def _cell(role: str, *, _cells: list[str] = cells) -> str:
            idx = roles.get(role)
            return _cells[idx].strip() if idx is not None and idx < len(_cells) else ""

        term_raw = strip_emphasis(_cell("term"))
        if not term_raw:
            continue
        primary = term_raw.split("/")[0].strip()
        meaning = _cell("meaning")
        why = _cell("why")
        example = _cell("example")

        fields = {
            "Term": md_to_html_inline(term_raw),
            "Meaning": md_to_html_inline(meaning) if meaning else "",
            "Why": md_to_html_inline(why) if why else "",
            "Example": md_to_html_inline(example) if example else "",
            "AIExamples": "",
            "SourceId": "",
        }
        card_id = f"vocab__{source_stem}__{_stable_hash(primary.lower())}"
        tags = base_tags + ([category_tag] if category_tag else [])
        cards.append(
            Card(
                id=card_id,
                deck=config.VOCAB_DECK,
                type=CardType.VOCAB,
                fields=fields,
                tags=tags,
                source=source,
                source_locator=category_tag or source_stem,
                source_hash=source_hash,
            )
        )
    return cards


def _read_qa(
    lines: list[str],
    start: int,
    *,
    section: str,
) -> tuple[str, str, int]:
    """Read one Q&A block. Returns (question, answer_markdown, next_index).

    An optional ``*italic lead-in*`` line may precede the answer. The answer
    itself starts as a blockquote (``>``-prefixed); once it has started,
    continuation lines — including further paragraphs that omit the ``>``
    prefix — are kept as part of the answer until a heading or a table ends
    the block. Blank lines between paragraphs are preserved so Markdown renders
    separate ``<p>`` blocks.
    """
    m = _Q_HEADING.match(lines[start])
    if m is None:
        return "", "", start + 1  # not actually a Q heading — skip
    question = m.group(1).strip().strip('"“”').strip()

    leadin = ""
    body: list[str] = []
    in_answer = False
    j = start + 1
    while j < len(lines):
        line = lines[j]
        if _HEADING.match(line):  # next heading ends the block
            break
        if _TABLE_ROW.match(line):  # a table is not part of an answer
            break
        if not in_answer:
            if line.strip() == "":
                j += 1
                continue
            mlead = _LEADIN.match(line)
            if mlead:
                leadin = line.strip()
                j += 1
                continue
            if line.lstrip().startswith(">"):
                in_answer = True
                body.append(line.lstrip()[1:].lstrip())
                j += 1
                continue
            # A non-quote line before any blockquote ends the (empty) answer.
            break
        # in_answer: accumulate the body until a heading/table ends it.
        if line.lstrip().startswith(">"):
            body.append(line.lstrip()[1:].lstrip())
        else:
            body.append(line.rstrip())
        j += 1

    answer_md = "\n".join(body).strip()
    if leadin:
        answer_md = f"{leadin}\n\n{answer_md}" if answer_md else leadin
    return question, answer_md, j


def _parse_qa(
    question: str,
    answer_md: str,
    *,
    source_stem: str,
    source: str,
    source_hash: str,
    section: str,
    base_tags: list[str],
) -> Card | None:
    if not answer_md.strip():
        return None
    answer_html = md_to_html_block(answer_md)
    card_id = f"qa__{source_stem}__{_stable_hash(question.lower())}"
    section_tag = heading_tag(section) if section else ""
    tags = base_tags + ([section_tag] if section_tag else [])
    return Card(
        id=card_id,
        deck=config.QA_DECK,
        type=CardType.QA,
        fields={
            "Section": section,
            "Question": md_to_html_inline(question),
            "Answer": answer_html,
            "Variants": "",
            "SourceId": "",
        },
        tags=tags,
        source=source,
        source_locator=section or source_stem,
        source_hash=source_hash,
    )


def extract_text(text: str, *, source: str = "") -> list[Card]:
    """Extract cards from Markdown text. ``source`` is an opaque path label."""
    lines = text.splitlines()
    source_stem = slugify(Path(source).stem) if source else "input"
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    base_tags = [source_stem]

    cards: list[Card] = []
    current_section = ""
    last_heading = ""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Check Q&A heading BEFORE general heading (### Q: is also a heading).
        if _Q_HEADING.match(line):
            question, answer_md, j = _read_qa(lines, i, section=current_section)
            card = _parse_qa(
                question,
                answer_md,
                source_stem=source_stem,
                source=source,
                source_hash=source_hash,
                section=current_section,
                base_tags=base_tags,
            )
            if card is not None:
                cards.append(card)
            i = j
            continue

        hm = _HEADING.match(line)
        if hm:
            level = len(hm.group(1))
            title = hm.group(2).strip()
            if level <= 2:
                current_section = title
            last_heading = title
            i += 1
            continue

        if _TABLE_ROW.match(line) and i + 1 < n and _is_separator(lines[i + 1]):
            # Only treat as a vocab table if the header looks like a Term table.
            header_cells = _split_row(line)
            looks_like_terms = any("term" in c.lower() for c in header_cells if c.strip())
            block, j = _read_table(lines, i)
            if looks_like_terms:
                cards.extend(
                    _parse_table(
                        block,
                        source_stem=source_stem,
                        source=source,
                        source_hash=source_hash,
                        category_tag=heading_tag(last_heading),
                        base_tags=base_tags,
                    )
                )
            i = j
            continue

        i += 1

    return cards


def extract_file(path: str | Path) -> list[Card]:
    """Extract cards from a Markdown file on disk."""
    p = Path(path)
    return extract_text(p.read_text(encoding="utf-8"), source=str(p))

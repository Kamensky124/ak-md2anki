"""Markdown helpers: slugify, heading→tag, and Markdown→HTML for Anki.

Anki renders note fields as HTML, so cell/answer text is converted with the
``markdown`` library. For short cell content we strip the wrapping ``<p>``
that ``markdown.markdown`` emits.
"""

from __future__ import annotations

import re

import markdown as _md

_INNER_P = re.compile(r"^<p>(.*)</p>\s*$", re.DOTALL)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
_PAREN = re.compile(r"\(([^()]*)\)")
_ASCII_LABEL = re.compile(r"^[A-Za-z0-9 &,\-/+]+$")


def slugify(text: str) -> str:
    """Lowercase alnum runs (including Unicode letters) joined by ``-``."""
    cleaned = re.sub(r"[^\w]+", "-", text.strip().lower()).replace("_", "-").strip("-")
    return cleaned or "section"


def strip_emphasis(text: str) -> str:
    """Remove ``**bold**`` / ``*italic*`` / `` `code` `` markers."""
    out = _BOLD.sub(r"\1", text)
    out = _ITALIC.sub(r"\1", out)
    out = re.sub(r"`([^`]+)`", r"\1", out)
    return out


def md_to_html_block(text: str) -> str:
    """Convert a block of Markdown to HTML (keeps ``<p>`` wrappers)."""
    return _md.markdown(text.strip()).strip()


def md_to_html_inline(text: str) -> str:
    """Convert short Markdown (a table cell) to HTML, stripping the ``<p>``."""
    html = md_to_html_block(text)
    m = _INNER_P.match(html)
    return m.group(1) if m else html


def heading_tag(title: str) -> str:
    """Derive a short, stable tag from a Markdown heading.

    Preference order:
    1. A short ASCII parenthetical label (e.g. ``(pricing & payment)`` → ``pricing-payment``).
    2. The text before a paren / em-dash (e.g. ``Stage 1 — Opening`` → ``stage-1``).
    """
    title = title.strip()
    paren = _PAREN.search(title)
    if paren:
        inner = paren.group(1).strip()
        if inner and len(inner.split()) <= 3 and _ASCII_LABEL.match(inner):
            return slugify(inner)
    base = _PAREN.sub("", title)
    base = re.split(r"[\u2014\u2013-]\s", base, maxsplit=1)[0]
    return slugify(base)

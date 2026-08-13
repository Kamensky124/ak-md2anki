"""Tests for --prose dispatch in the build command.

Prose extraction must only run when a file yields no structured cards: both
extractors share the same id scheme, so running both on one file would emit
duplicate ids.
"""

import argparse

from ak_md2anki.cli import cmd_build
from ak_md2anki.store import load


def _ns(path, out, *, prose=False) -> argparse.Namespace:
    return argparse.Namespace(
        path=str(path),
        out=str(out),
        prose=prose,
        no_enrich=True,
        force=False,
        verbose=False,
        cache_file=None,
        no_cache=True,
    )


def test_prose_skipped_when_structured_present(tmp_path, monkeypatch):
    import ak_md2anki.cli as cli

    md = tmp_path / "v.md"
    md.write_text("| Term | Meaning |\n|---|---|\n| Retainer | fee |\n", encoding="utf-8")
    out = tmp_path / "cards.json"

    calls = {"n": 0}

    def spy(text, *, source=""):
        calls["n"] += 1
        return []

    monkeypatch.setattr(cli, "extract_prose", spy)

    cmd_build(_ns(md, out, prose=True))

    assert calls["n"] == 0
    cards = load(out)
    assert len(cards) == 1
    assert cards[0].fields["Term"] == "Retainer"


def test_prose_runs_when_no_structured(tmp_path, monkeypatch):
    import ak_md2anki.cli as cli

    md = tmp_path / "notes.md"
    md.write_text("# Notes\nJust prose, no tables or Q blocks.\n", encoding="utf-8")
    out = tmp_path / "cards.json"

    calls = {"n": 0}

    def spy(text, *, source=""):
        calls["n"] += 1
        return []

    monkeypatch.setattr(cli, "extract_prose", spy)

    cmd_build(_ns(md, out, prose=True))

    assert calls["n"] == 1

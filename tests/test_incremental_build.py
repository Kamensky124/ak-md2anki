"""Tests for incremental build using source_hash."""

import argparse

from ak_md2anki.cli import cmd_build
from ak_md2anki.store import load


def test_incremental_build_skips_unchanged_files(tmp_path, capsys):
    md_file = tmp_path / "vocab.md"
    md_file.write_text(
        "| Term | Meaning |\n|---|---|\n| Retainer | Monthly fee |\n",
        encoding="utf-8",
    )
    cards_out = tmp_path / "cards.json"

    # First build: should parse and write 1 card.
    args1 = argparse.Namespace(
        path=str(md_file),
        out=str(cards_out),
        no_enrich=True,
        force=False,
        verbose=False,
        cache_file=None,
        no_cache=True,
    )
    cmd_build(args1)

    cards1 = load(cards_out)
    assert len(cards1) == 1
    assert cards1[0].fields["Term"] == "Retainer"

    # Second build with unchanged file: should reuse cached card.
    args2 = argparse.Namespace(
        path=str(md_file),
        out=str(cards_out),
        no_enrich=True,
        force=False,
        verbose=False,
        cache_file=None,
        no_cache=True,
    )
    cmd_build(args2)

    captured = capsys.readouterr()
    assert "1 reused" in captured.out

    # Modify file content: should re-parse file.
    md_file.write_text(
        "| Term | Meaning |\n|---|---|\n| Retainer | Monthly fee |\n| SOW | Scope |\n",
        encoding="utf-8",
    )
    cmd_build(args2)

    cards3 = load(cards_out)
    assert len(cards3) == 2


def test_force_build_rebuilds_all(tmp_path, capsys):
    md_file = tmp_path / "vocab.md"
    md_file.write_text(
        "| Term | Meaning |\n|---|---|\n| Retainer | Monthly fee |\n",
        encoding="utf-8",
    )
    cards_out = tmp_path / "cards.json"

    args = argparse.Namespace(
        path=str(md_file),
        out=str(cards_out),
        no_enrich=True,
        force=False,
        verbose=False,
        cache_file=None,
        no_cache=True,
    )
    cmd_build(args)

    # Re-run with --force: should not show reused.
    args_force = argparse.Namespace(
        path=str(md_file),
        out=str(cards_out),
        no_enrich=True,
        force=True,
        verbose=False,
        cache_file=None,
        no_cache=True,
    )
    cmd_build(args_force)
    captured = capsys.readouterr()
    assert "reused" not in captured.out

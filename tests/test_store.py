"""Tests for cards.json store."""

import json
import tempfile
from pathlib import Path

from ak_md2anki.models import Card, CardType
from ak_md2anki.store import load, save


def _make_card(card_id: str) -> Card:
    return Card(
        id=card_id,
        deck="Test::Deck",
        type=CardType.VOCAB,
        fields={"Term": "test", "Meaning": "meaning"},
        tags=["test"],
    )


class TestStore:
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cards.json"
            orig = [_make_card("a"), _make_card("b")]
            save(path, orig)
            loaded = load(path)
            assert len(loaded) == 2
            assert {c.id for c in loaded} == {"a", "b"}

    def test_load_missing_file(self):
        assert load("/tmp/does-not-exist-cards.json") == []

    def test_load_empty_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "empty.json"
            path.write_text("")
            assert load(path) == []

    def test_load_invalid_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{")
            assert load(path) == []

    def test_save_is_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cards.json"
            cards = [_make_card("c"), _make_card("a"), _make_card("b")]
            save(path, cards)
            loaded = load(path)
            ids = [c.id for c in loaded]
            assert ids == sorted(ids)

    def test_save_dedupes_by_id(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cards.json"
            first = _make_card("dup")
            first.fields["Term"] = "first"
            second = _make_card("dup")
            second.fields["Term"] = "second"
            save(path, [first, second])
            loaded = load(path)
            assert len(loaded) == 1
            assert loaded[0].fields["Term"] == "first"

    def test_load_skips_malformed_card(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cards.json"
            good = _make_card("good").to_dict()
            bad = {**good, "id": "x", "type": "not-a-real-type"}
            path.write_text(json.dumps({"cards": [good, bad]}), encoding="utf-8")
            loaded = load(path)
            assert len(loaded) == 1
            assert loaded[0].id == "good"

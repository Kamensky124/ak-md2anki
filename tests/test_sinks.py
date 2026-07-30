"""Tests for AnkiConnect and APKG sinks."""


import pytest
import requests

from ak_md2anki.models import Card, CardType
from ak_md2anki.sink.ankiconnect import sync_cards
from ak_md2anki.sink.apkg import export_apkg


def _sample_cards() -> list[Card]:
    return [
        Card(
            id="vocab__test__hash1",
            deck="Test::Vocab",
            type=CardType.VOCAB,
            fields={
                "Term": "SOW",
                "Meaning": "Statement of Work",
                "Why": "",
                "Example": "",
                "AIExamples": "",
                "SourceId": "vocab__test__hash1",
            },
            tags=["test"],
        ),
        Card(
            id="qa__test__hash2",
            deck="Test::QA",
            type=CardType.QA,
            fields={
                "Section": "Scoping",
                "Question": "What is timeline?",
                "Answer": "2 weeks",
                "Variants": "",
                "SourceId": "qa__test__hash2",
            },
            tags=["test"],
        ),
    ]


class TestApkgSink:
    def test_export_apkg(self, tmp_path):
        cards = _sample_cards()
        out_file = tmp_path / "output.apkg"
        export_apkg(cards, out_file)
        assert out_file.exists()
        assert out_file.stat().st_size > 0


class TestAnkiConnectSink:
    def test_sync_cards_dry_run(self, monkeypatch):
        cards = _sample_cards()

        def mock_post(url, json=None, timeout=None):
            action = json.get("action")
            class MockResponse:
                def raise_for_status(self):
                    pass
                def json(self):
                    if action in ("modelNames", "deckNames"):
                        return {"result": [], "error": None}
                    if action == "findNotes":
                        return {"result": [], "error": None}
                    return {"result": None, "error": None}

            return MockResponse()

        monkeypatch.setattr(requests, "post", mock_post)
        counts = sync_cards(cards, dry_run=True)
        assert counts["added"] == 2
        assert counts["updated"] == 0

    def test_sync_cards_empty(self):
        counts = sync_cards([])
        assert counts == {"added": 0, "updated": 0, "skipped": 0}

    def test_connection_error(self, monkeypatch):
        def mock_post(*args, **kwargs):
            raise requests.ConnectionError("Connection refused")

        monkeypatch.setattr(requests, "post", mock_post)
        with pytest.raises(RuntimeError, match="Cannot reach AnkiConnect"):
            sync_cards(_sample_cards())

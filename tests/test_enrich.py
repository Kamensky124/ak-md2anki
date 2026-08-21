"""Tests for OpenRouter enrichment (HTTP is mocked — no live calls)."""

import requests

from ak_md2anki.enrich import _call_openrouter, _extract_json, _normalize_text, enrich
from ak_md2anki.models import Card, CardType


def _make_vocab(card_id: str, term: str) -> Card:
    return Card(
        id=card_id,
        deck="Test::Vocab",
        type=CardType.VOCAB,
        fields={
            "Term": term,
            "Meaning": "some meaning",
            "Why": "",
            "Example": "an example",
            "AIExamples": "",
            "SourceId": "",
        },
        tags=[],
    )


def _make_qa(card_id: str, question: str, answer: str) -> Card:
    return Card(
        id=card_id,
        deck="Test::QA",
        type=CardType.QA,
        fields={
            "Section": "",
            "Question": question,
            "Answer": answer,
            "Variants": "",
            "SourceId": "",
        },
        tags=[],
    )


class TestEnrichNoKey:
    """When OPENROUTER_API_KEY is absent, enrich is a no-op."""

    def test_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        cards = [_make_vocab("v1", "retainer")]
        result = enrich(cards, cache_enabled=False)
        assert not result[0].enriched
        assert result[0].fields["AIExamples"] == ""


class TestEnrichWithMock:
    """With a fake key + mocked HTTP, cards get enriched."""

    def _mock_openrouter(self, monkeypatch, return_value=None):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        import ak_md2anki.enrich as mod

        def fake_call(messages, model):
            if return_value is not None:
                return return_value
            return {
                "choices": [
                    {"message": {"content": '[{"term":"retainer","examples":["ex1","ex2"]}]'}}
                ]
            }

        monkeypatch.setattr(mod, "_call_openrouter", fake_call)

    def test_vocab_enrichment(self, monkeypatch, tmp_path):
        self._mock_openrouter(monkeypatch)
        cards = [_make_vocab("v1", "retainer")]
        cache_file = tmp_path / "cache.json"
        result = enrich(cards, cache_path=cache_file)
        assert result[0].enriched
        assert "ex1" in result[0].fields["AIExamples"]

    def test_html_formatting_matching(self, monkeypatch, tmp_path):
        """Terms with HTML like <strong>retainer</strong> should match LLM plain term."""
        self._mock_openrouter(monkeypatch)
        cards = [_make_vocab("v1", "<strong>retainer</strong>")]
        cache_file = tmp_path / "cache.json"
        result = enrich(cards, cache_path=cache_file)
        assert result[0].enriched
        assert "ex1" in result[0].fields["AIExamples"]

    def test_qa_enrichment(self, monkeypatch, tmp_path):
        import ak_md2anki.enrich as mod

        def fake_call(messages, model):
            return {
                "choices": [
                    {"message": {"content": '[{"question":"What is X?","variants":["v1","v2"]}]'}}
                ]
            }

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        monkeypatch.setattr(mod, "_call_openrouter", fake_call)
        cards = [_make_qa("q1", "What is X?", "It is Y.")]
        cache_file = tmp_path / "cache.json"
        result = enrich(cards, cache_path=cache_file)
        assert result[0].enriched
        assert "v1" in result[0].fields["Variants"]

    def test_caching(self, monkeypatch, tmp_path):
        import ak_md2anki.enrich as mod

        call_count = [0]

        def fake_call(messages, model):
            call_count[0] += 1
            return {
                "choices": [
                    {"message": {"content": '[{"term":"retainer","examples":["c1","c2"]}]'}}
                ]
            }

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        monkeypatch.setattr(mod, "_call_openrouter", fake_call)

        cache_file = tmp_path / "cache.json"
        cards = [_make_vocab("v1", "retainer")]
        result1 = enrich(cards, cache_path=cache_file)
        assert result1[0].enriched
        assert call_count[0] == 1

        # Second run: should hit cache, no extra call.
        cards2 = [_make_vocab("v1", "retainer")]
        result2 = enrich(cards2, cache_path=cache_file)
        assert result2[0].enriched
        assert call_count[0] == 1  # still 1 — cached

    def test_empty_json_array_handling(self):
        res = _extract_json({"choices": [{"message": {"content": "[]"}}]})
        assert res == []

    def test_normalize_text(self):
        assert _normalize_text("<strong>foo &amp; bar</strong>") == "foo & bar"

    def test_http_retry_failure(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        attempts = [0]

        def mock_post(*args, **kwargs):
            attempts[0] += 1
            raise requests.RequestException("Network error")

        monkeypatch.setattr(requests, "post", mock_post)
        res = _call_openrouter([{"role": "user", "content": "hi"}], "test-model", retries=1)
        assert res is None
        assert attempts[0] == 2

    def test_enrichment_escapes_html_in_examples(self, monkeypatch, tmp_path):
        """Untrusted LLM output must be HTML-escaped before reaching Anki fields."""
        import ak_md2anki.enrich as mod

        def fake_call(messages, model):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '[{"term":"retainer","examples":['
                            '"<script>alert(1)</script>","ok"]}]'
                        }
                    }
                ]
            }

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        monkeypatch.setattr(mod, "_call_openrouter", fake_call)
        cards = [_make_vocab("v1", "retainer")]
        result = enrich(cards, cache_path=tmp_path / "cache.json")
        field = result[0].fields["AIExamples"]
        assert "<script>" not in field
        assert "&lt;script&gt;" in field

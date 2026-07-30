"""Tests for OpenRouter enrichment (HTTP is mocked — no live calls)."""

from ak_md2anki.enrich import enrich
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
        result = enrich(cards)
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
            return {"choices": [{"message": {"content": '[{"term":"retainer","examples":["ex1","ex2"]}]'}}]}

        monkeypatch.setattr(mod, "_call_openrouter", fake_call)

    def test_vocab_enrichment(self, monkeypatch):
        self._mock_openrouter(monkeypatch)
        cards = [_make_vocab("v1", "retainer")]
        result = enrich(cards)
        assert result[0].enriched
        assert "ex1" in result[0].fields["AIExamples"]

    def test_qa_enrichment(self, monkeypatch):
        import ak_md2anki.enrich as mod

        def fake_call(messages, model):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '[{"question":"What is X?","variants":["v1","v2"]}]'
                        }
                    }
                ]
            }

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        monkeypatch.setattr(mod, "_call_openrouter", fake_call)
        cards = [_make_qa("q1", "What is X?", "It is Y.")]
        result = enrich(cards)
        assert result[0].enriched
        assert "v1" in result[0].fields["Variants"]

    def test_caching(self, monkeypatch, tmp_path):
        import ak_md2anki.enrich as mod

        call_count = [0]

        def fake_call(messages, model):
            call_count[0] += 1
            return {"choices": [{"message": {"content": '[{"term":"retainer","examples":["c1","c2"]}]'}}]}

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
        monkeypatch.setattr(mod, "_call_openrouter", fake_call)
        # Use a temp cache file.
        cache = tmp_path / "cache.json"
        monkeypatch.setattr(mod, "_cache_path", lambda: cache)

        cards = [_make_vocab("v1", "retainer")]
        result1 = enrich(cards)
        assert result1[0].enriched
        assert call_count[0] == 1

        # Second run: should hit cache, no extra call.
        cards2 = [_make_vocab("v1", "retainer")]
        result2 = enrich(cards2)
        assert result2[0].enriched
        assert call_count[0] == 1  # still 1 — cached

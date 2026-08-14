"""Tests for LLM prose extractor (extract/prose.py)."""

from ak_md2anki.extract.prose import _chunk_text, extract_prose


def test_chunk_text_and_skip_comment():
    text = """## Section 1
Some prose content.

## Section 2
<!-- anki:skip -->
Skipped content.
"""
    chunks = _chunk_text(text)
    assert len(chunks) == 2
    assert "Section 1" in chunks[0][0]
    assert "<!-- anki:skip -->" in chunks[1][1]


def test_prose_extractor_no_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cards = extract_prose("Some raw prose text without key")
    assert cards == []


def test_prose_extractor_mocked(monkeypatch):
    import ak_md2anki.extract.prose as mod

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")

    def mock_call(messages, model):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "["
                            '{"type": "vocab", "term": "API", "meaning": "Application Programming Interface", "why": "", "example": ""},'
                            '{"type": "qa", "section": "Tech", "question": "What is REST?", "answer": "Representational State Transfer"}'
                            "]"
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(mod, "_call_openrouter", mock_call)

    text = "## Tech\n\nAPI is Application Programming Interface. REST is Representational State Transfer."
    cards = extract_prose(text, source="tech_notes.md")

    assert len(cards) == 2
    vocab_card = next(c for c in cards if c.type.value == "vocab")
    qa_card = next(c for c in cards if c.type.value == "qa")

    assert vocab_card.fields["Term"] == "API"
    assert vocab_card.fields["Meaning"] == "Application Programming Interface"
    assert qa_card.fields["Question"] == "What is REST?"
    assert qa_card.fields["Answer"] == "<p>Representational State Transfer</p>"


def test_prose_respects_rpm_between_chunks(monkeypatch):
    import ak_md2anki.extract.prose as mod

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    sleeps: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: sleeps.append(s))

    def mock_call(messages, model):
        return {"choices": [{"message": {"content": "[]"}}]}

    monkeypatch.setattr(mod, "_call_openrouter", mock_call)

    text = "## A\nprose\n\n## B\nprose\n\n## C\nprose\n"
    cards = extract_prose(text, source="multi.md")

    assert cards == []
    # 3 chunks → 2 inter-chunk sleeps (none after the last).
    assert len(sleeps) == 2


def test_prose_escapes_html_in_llm_fields(monkeypatch):
    """Untrusted LLM output in prose fields must be HTML-escaped."""
    import ak_md2anki.extract.prose as mod

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    monkeypatch.setattr(
        mod,
        "_call_openrouter",
        lambda messages, model: {
            "choices": [
                {
                    "message": {
                        "content": '[{"type":"vocab","term":"API",'
                        '"meaning":"<script>x</script>","why":"","example":""}]'
                    }
                }
            ]
        },
    )
    cards = extract_prose("## Tech\nAPI.", source="t.md")
    assert len(cards) == 1
    meaning = cards[0].fields["Meaning"]
    assert "<script>" not in meaning
    assert "&lt;script&gt;" in meaning

"""Tests for the structured Markdown extractor."""

from pathlib import Path

from ak_md2anki.extract import extract_file, extract_text
from ak_md2anki.models import CardType

FIXTURES = Path(__file__).parent / "fixtures"
VOCAB_MD = FIXTURES / "sample_vocab.md"
QA_MD = FIXTURES / "sample_qa.md"


class TestExtractVocab:
    def test_extract_file_returns_cards(self):
        cards = extract_file(VOCAB_MD)
        assert len(cards) > 0
        assert all(c.type == CardType.VOCAB for c in cards)

    def test_count(self):
        cards = extract_file(VOCAB_MD)
        # fixture has 4 table rows across 2 tables
        assert len(cards) == 4

    def test_ids_are_stable(self):
        run1 = extract_file(VOCAB_MD)
        run2 = extract_file(VOCAB_MD)
        assert [c.id for c in run1] == [c.id for c in run2]

    def test_term_fields(self):
        cards = extract_file(VOCAB_MD)
        retainer = next(
            c for c in cards if "retainer" in (c.fields.get("Term") or "").lower()
        )
        assert retainer.type == CardType.VOCAB
        assert "retainer" in retainer.fields["Term"].lower()
        assert "monthly prepayment" in retainer.fields["Meaning"].lower()
        assert "maintenance runs" in retainer.fields["Example"].lower()

    def test_fixed_price_has_slash_variants(self):
        cards = extract_file(VOCAB_MD)
        fp = next(
            c for c in cards if "fixed-price" in (c.fields.get("Term") or "").lower()
        )
        assert "/" in fp.fields["Term"] or "fixed bid" in fp.fields["Term"].lower()

    def test_milestone_payment_has_why(self):
        cards = extract_file(VOCAB_MD)
        mp = next(
            c for c in cards if "milestone" in (c.fields.get("Term") or "").lower()
        )
        assert mp.fields.get("Why", "")

    def test_tags(self):
        cards = extract_file(VOCAB_MD)
        retainer = next(
            c for c in cards if "retainer" in (c.fields.get("Term") or "").lower()
        )
        assert any("engagement" in t.lower() for t in retainer.tags)

    def test_deck_is_vocab(self):
        cards = extract_file(VOCAB_MD)
        assert all("Vocab" in c.deck for c in cards)

    def test_source_and_hash_populated(self):
        cards = extract_file(VOCAB_MD)
        for c in cards:
            assert c.source.endswith(".md")
            assert len(c.source_hash) == 64  # sha256 hex

    def test_freeform_paragraphs_skipped(self):
        cards = extract_file(VOCAB_MD)
        # verify we didn't accidentally pull in prose text as cards
        for c in cards:
            assert "free-form" not in c.fields.get("Term", "").lower()


class TestExtractQA:
    def test_count(self):
        cards = extract_file(QA_MD)
        # fixture has 3 Q blocks (background, industry, project walkthrough)
        assert len(cards) == 3

    def test_ids_are_stable(self):
        run1 = extract_file(QA_MD)
        run2 = extract_file(QA_MD)
        assert [c.id for c in run1] == [c.id for c in run2]

    def test_question_fields(self):
        cards = extract_file(QA_MD)
        bg = next(
            c
            for c in cards
            if "background" in (c.fields.get("Question") or "").lower()
        )
        assert bg.type == CardType.QA
        assert "background" in bg.fields["Question"].lower()
        assert "independent" in bg.fields["Answer"].lower()

    def test_industry_question_has_leadin(self):
        cards = extract_file(QA_MD)
        ind = next(
            c
            for c in cards
            if "industry" in (c.fields.get("Question") or "").lower()
        )
        html = ind.fields["Answer"]
        assert "even if no" in html.lower() or "Even" in html

    def test_walkthrough_question_has_answer(self):
        cards = extract_file(QA_MD)
        walk = next(
            c
            for c in cards
            if "walk" in (c.fields.get("Question") or "").lower()
        )
        assert "current-state" in walk.fields["Answer"].lower() or "review" in walk.fields["Answer"].lower()

    def test_section_field(self):
        cards = extract_file(QA_MD)
        bg = next(
            c
            for c in cards
            if "background" in (c.fields.get("Question") or "").lower()
        )
        assert bg.fields.get("Section", "")  # should have the ## heading

    def test_bullet_sections_skipped(self):
        cards = extract_file(QA_MD)
        # section H has bullets, no ### Q: — should produce zero cards from it
        questions = [c.fields.get("Question") for c in cards]
        assert not any("new lead" in (q or "").lower() for q in questions)

    def test_deck_is_qa(self):
        cards = extract_file(QA_MD)
        assert all("QA" in c.deck for c in cards)


class TestExtractionFromString:
    def test_extract_text_accepts_source_label(self):
        text = VOCAB_MD.read_text()
        cards = extract_text(text, source="inline://vocab")
        assert len(cards) == 4
        assert cards[0].source == "inline://vocab"

    def test_empty_text(self):
        assert extract_text("", source="empty") == []

    def test_no_structure_text(self):
        assert extract_text("Just some prose.", source="prose") == []

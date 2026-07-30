"""Tests for mdutil helpers."""

from ak_md2anki.mdutil import (
    heading_tag,
    md_to_html_block,
    md_to_html_inline,
    slugify,
    strip_emphasis,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("foo & bar, baz") == "foo-bar-baz"

    def test_non_ascii_dropped(self):
        assert slugify("привет") == "" or slugify("привет") == "section"


class TestStripEmphasis:
    def test_bold(self):
        assert strip_emphasis("**hello**") == "hello"

    def test_bold_with_slash(self):
        assert strip_emphasis("**fixed-price** / **fixed bid**") == "fixed-price / fixed bid"

    def test_italic(self):
        assert strip_emphasis("*even*") == "even"

    def test_code(self):
        assert strip_emphasis("`code`") == "code"


class TestMdToHtml:
    def test_inline_strips_p(self):
        result = md_to_html_inline("hello")
        assert "<p>" not in result

    def test_inline_bold(self):
        result = md_to_html_inline("**hello**")
        assert "<strong>hello</strong>" in result.lower()

    def test_block_keeps_p(self):
        result = md_to_html_block("Hello")
        assert "<p>" in result


class TestHeadingTag:
    def test_paren_label(self):
        assert heading_tag("Деньги и оплата (pricing & payment)") == "pricing-payment"

    def test_engagement(self):
        assert heading_tag("Процесс и взаимодействие (engagement)") == "engagement"

    def test_stage(self):
        # "the first 5 minutes" is 4 words → falls back to "Stage 1"
        tag = heading_tag("Stage 1 — Opening & fit (the first 5 minutes)")
        assert "stage" in tag

    def test_about_credibility(self):
        tag = heading_tag("A. About you & credibility")
        assert "about" in tag.lower()

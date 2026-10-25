"""Escaped HTML presentation of analyzed article text, independent of parsing."""

from html import escape

from kanji_vocab_miner.article_reader import ArticleToken
from kanji_vocab_miner.furigana import render_token_furigana


def _render_token_html(token: ArticleToken, known_kanji: set[str] | None) -> str:
    """Render one analyzed token; whitespace between tokens is handled separately."""
    if not token.surface:
        return ""
    classes = ["token", "known" if token.is_known else "unknown"]
    if token.is_vocabulary and token.jlpt_level is not None:
        classes.append(f"jlpt-n{token.jlpt_level}")
    title = ""
    if token.name_kind:
        classes.extend(["name", f"name-{token.name_kind}"])
        label = "Person name" if token.name_kind == "person" else "Place name"
        title = f' title="{label}"'
    content = render_token_furigana(
        token.surface, token.reading, known_kanji, known_class="known-kanji"
    )
    return f'<span class="{" ".join(classes)}"{title}>{content}</span>'


def render_article_html(
    tokens: list[ArticleToken], known_kanji: set[str] | None = None
) -> str:
    """Render only the article text, highlighting and ruby as escaped HTML.

    Vocabulary counts/groups come from build_unknown_vocabulary_summary; the
    page template renders that separate list. This function does neither.
    """
    return "".join(
        escape(token.leading_whitespace) + _render_token_html(token, known_kanji)
        for token in tokens
    )

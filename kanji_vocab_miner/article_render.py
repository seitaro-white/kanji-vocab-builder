"""Escaped HTML presentation of analyzed article text, independent of parsing."""

from collections.abc import Iterator
from html import escape

from kanji_vocab_miner.article_reader import ArticleToken
from kanji_vocab_miner.furigana import render_token_furigana

# A bounded display policy, not a replacement for Sudachi's morphological tokens.
_INFLECTION_AUXILIARIES = {
    "た", "ます", "です", "ない", "ぬ", "れる", "られる", "せる", "させる", "たい",
}


def _iter_display_groups(tokens: list[ArticleToken]) -> Iterator[list[ArticleToken]]:
    """Group adjacent inflection endings for display, retaining native tokens."""
    group: list[ArticleToken] = []
    for token in tokens:
        if group and _can_extend_inflection(group[0], group[-1], token):
            group.append(token)
        else:
            if group:
                yield group
            group = [token]
    if group:
        yield group


def _can_extend_inflection(
    head: ArticleToken, previous: ArticleToken, ending: ArticleToken
) -> bool:
    if (
        not head.is_vocabulary
        or not head.part_of_speech
        or head.part_of_speech.category not in {"動詞", "形容詞"}
        or ending.leading_whitespace
        or ending.start != previous.end
        or not previous.part_of_speech
        or previous.part_of_speech.category not in {"動詞", "形容詞", "助動詞"}
        or not ending.part_of_speech
    ):
        return False
    pos = ending.part_of_speech
    identity = ending.identities[0] if ending.identities else None
    if pos.category == "助動詞":
        return identity in _INFLECTION_AUXILIARIES
    if (
        pos.category == "形容詞"
        and pos.subcategory == "非自立可能"
        and identity == "ない"
    ):
        return (
            head.part_of_speech.category == "形容詞"
            and previous.part_of_speech.conjugation_form.startswith("連用形")
        )
    return (
        pos.category == "助詞"
        and pos.subcategory == "接続助詞"
        and ending.surface in {"て", "で"}
        and previous.part_of_speech.conjugation_form.startswith("連用形")
    )


def _render_group_html(
    group: list[ArticleToken], known_kanji: set[str] | None
) -> str:
    """Render a display group using its lexical head's vocabulary metadata."""
    token = group[0]
    if not token.surface:
        return ""
    classes = ["token", "known" if token.is_known else "unknown"]
    if token.is_vocabulary and token.jlpt_level is not None:
        classes.append(f"jlpt-n{token.jlpt_level}")
    # Reader-only metadata: 0 means unlisted, not an easier JLPT level.
    reading_level = ""
    if token.is_vocabulary and not token.is_known:
        reading_level = f' data-reading-level="{token.jlpt_level or 0}"'
    title = ""
    if token.name_kind:
        classes.extend(["name", f"name-{token.name_kind}"])
        label = "Person name" if token.name_kind == "person" else "Place name"
        title = f' title="{label}"'
    content = "".join(
        render_token_furigana(
            member.surface, member.reading, known_kanji, known_class="known-kanji"
        )
        for member in group
    )
    return f'<span class="{" ".join(classes)}"{title}{reading_level}>{content}</span>'


def render_article_html(
    tokens: list[ArticleToken], known_kanji: set[str] | None = None
) -> str:
    """Render article text with reader-only inflection highlight groups and ruby.

    Native tokens and readings remain separate; only the outer highlight groups
    common adjacent endings with a kanji verb/adjective's vocabulary metadata.
    Vocabulary counts/groups come from build_unknown_vocabulary_summary; the
    page template renders that separate list. This function does neither.
    """
    return "".join(
        escape(group[0].leading_whitespace) + _render_group_html(group, known_kanji)
        for group in _iter_display_groups(tokens)
    )

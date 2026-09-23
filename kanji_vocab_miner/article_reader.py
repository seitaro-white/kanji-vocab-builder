"""Pure analysis and safe HTML rendering for pasted Japanese articles."""

from dataclasses import dataclass
from functools import lru_cache
from html import escape
import re
import unicodedata

from fugashi import UnidicNode

from kanji_vocab_miner.furigana import (
    _get_tagger,
    _to_hiragana,
    render_token_furigana,
)
from kanji_vocab_miner.jlpt import get_level_index

_JAPANESE_WORD_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
_EXCLUDED_DICTIONARY_PARTS = {"助詞", "助動詞", "補助記号", "記号"}
_EXCLUDED_HIGHLIGHT_PARTS = {"助詞", "助動詞"}


@dataclass(frozen=True)
class ArticleToken:
    """One analyzed morphological token and its display metadata."""

    surface: str
    leading_whitespace: str
    reading: str | None
    identities: tuple[str, ...]
    is_known: bool
    jlpt_level: int | None
    part_of_speech: str | None = None


@dataclass(frozen=True)
class UnknownWordEntry:
    """One canonical unknown vocabulary item and its article frequency."""

    expression: str
    count: int


@dataclass(frozen=True)
class UnknownWordGroup:
    """Unknown vocabulary entries sharing one JLPT level."""

    jlpt_level: int | None
    entries: tuple[UnknownWordEntry, ...]


def normalize_identity(value: str) -> str:
    """Normalize Unicode and compare kana identities in hiragana."""
    return _to_hiragana(unicodedata.normalize("NFKC", value).strip())


def token_identities(token: UnidicNode) -> tuple[str, ...]:
    """Return unique lemma, dictionary spelling, kana, and surface identities."""
    candidates = (
        token.feature.lemma,
        token.feature.orthBase,
        token.feature.kanaBase,
        str(token),
    )
    return tuple(
        dict.fromkeys(
            normalize_identity(candidate)
            for candidate in candidates
            if candidate and candidate != "*"
        )
    )


@lru_cache(maxsize=1)
def _normalized_jlpt_index() -> dict[str, int]:
    """Return the word-level JLPT index using article identity normalization."""
    normalized: dict[str, int] = {}
    for identity, level in get_level_index().items():
        normalized.setdefault(normalize_identity(identity), level)
    return normalized


def analyze_article(text: str, known_words: set[str]) -> list[ArticleToken]:
    """Tokenize ``text`` and classify each token for article display."""
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = re.sub(r"\n(?:[ \t]*\n)+", "\n\n", normalized_text)
    parsed_tokens = list(_get_tagger()(normalized_text))
    normalized_known_words = {normalize_identity(word) for word in known_words}
    jlpt_index = _normalized_jlpt_index()
    tokens: list[ArticleToken] = []
    for token in parsed_tokens:
        identities = token_identities(token)
        part_of_speech = token.feature.pos1
        jlpt_level = (
            None
            if part_of_speech in _EXCLUDED_HIGHLIGHT_PARTS
            else next(
                (
                    jlpt_index[identity]
                    for identity in identities
                    if identity in jlpt_index
                ),
                None,
            )
        )
        tokens.append(
            ArticleToken(
                surface=str(token),
                leading_whitespace=token.white_space,
                reading=(
                    None
                    if token.feature.kana in (None, "*")
                    else _to_hiragana(token.feature.kana)
                ),
                identities=identities,
                is_known=any(
                    identity in normalized_known_words for identity in identities
                ),
                jlpt_level=jlpt_level,
                part_of_speech=part_of_speech,
            )
        )
    consumed_length = sum(
        len(token.white_space) + len(str(token)) for token in parsed_tokens
    )
    if suffix := normalized_text[consumed_length:]:
        tokens.append(ArticleToken("", suffix, None, (), False, None))
    return tokens


def build_unknown_dictionary(
    tokens: list[ArticleToken],
) -> list[UnknownWordGroup]:
    """Group canonical unknown vocabulary and count occurrences."""
    grouped_counts: dict[int | None, dict[str, int]] = {}
    for token in tokens:
        if (
            token.is_known
            or not token.surface
            or not token.identities
            or not _JAPANESE_WORD_RE.search(token.surface)
            or token.part_of_speech in _EXCLUDED_DICTIONARY_PARTS
        ):
            continue
        expression = token.identities[0]
        counts = grouped_counts.setdefault(token.jlpt_level, {})
        counts[expression] = counts.get(expression, 0) + 1

    return [
        UnknownWordGroup(
            jlpt_level=level,
            entries=tuple(
                UnknownWordEntry(expression, count)
                for expression, count in sorted(
                    grouped_counts[level].items(), key=lambda item: -item[1]
                )
            ),
        )
        for level in (5, 4, 3, 2, 1, None)
        if level in grouped_counts
    ]


def render_article_html(tokens: list[ArticleToken]) -> str:
    """Render analyzed tokens as escaped application-owned HTML."""
    rendered: list[str] = []
    for token in tokens:
        rendered.append(escape(token.leading_whitespace))
        if not token.surface:
            continue
        classes = ["token", "known" if token.is_known else "unknown"]
        if token.jlpt_level is not None:
            classes.append(f"jlpt-n{token.jlpt_level}")
        content = render_token_furigana(token.surface, token.reading)
        rendered.append(f'<span class="{" ".join(classes)}">{content}</span>')
    return "".join(rendered)

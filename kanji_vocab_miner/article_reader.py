"""Analyze Japanese articles and aggregate unknown vocabulary, without HTML output."""

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from threading import local

from sudachipy import dictionary, morpheme, tokenizer
from sudachipy.errors import SudachiError

from kanji_vocab_miner.furigana import _KANJI_RE, _to_hiragana
from kanji_vocab_miner.jlpt import get_level_index

_EXCLUDED_VOCABULARY_PARTS = {
    "助詞",      # Particles, e.g. は and を.
    "助動詞",    # Auxiliaries, e.g. た and ます.
    "接尾辞",    # Standalone suffixes, e.g. っぽい.
    "接頭辞",    # Standalone prefixes, e.g. お.
    "補助記号",  # Punctuation.
    "記号",      # Other symbols.
    "空白",      # Whitespace.
}


@dataclass(frozen=True)
class PartOfSpeech:
    """Named fields of Sudachi's six-element POS tuple, in its native order.

    For 山田: category=名詞 (noun), subcategory=固有名詞 (proper noun),
    subclass=人名 (person), detail=姓 (surname). Unused fields contain '*'.
    """

    category: str
    subcategory: str
    subclass: str
    detail: str
    conjugation_type: str
    conjugation_form: str


def _is_vocabulary(surface: str, part_of_speech: PartOfSpeech | None) -> bool:
    category = part_of_speech.category if part_of_speech else None
    return bool(_KANJI_RE.search(surface)) and (
        category not in _EXCLUDED_VOCABULARY_PARTS
    )


@dataclass(frozen=True)
class ArticleToken:
    """One native token with vocabulary metadata and source offsets.

    ``surface`` is the original text as written, e.g. 食べ, unlike its lookup
    identity 食べる or reading たべ. HTML rendering lives in article_render.py.
    """

    surface: str
    leading_whitespace: str
    reading: str | None
    identities: tuple[str, ...]
    is_known: bool
    jlpt_level: int | None
    part_of_speech: PartOfSpeech | None = None
    name_kind: str | None = None
    start: int = 0
    end: int = 0

    @property
    def is_vocabulary(self) -> bool:
        """Whether this token is eligible for vocabulary colour and listing."""
        return not self.name_kind and _is_vocabulary(
            self.surface, self.part_of_speech
        )


@dataclass(frozen=True)
class VocabularyCount:
    """One normalized dictionary form and its article frequency, e.g. 食べる and 3."""

    dictionary_form: str
    occurrence_count: int


@dataclass(frozen=True)
class JlptVocabularyGroup:
    """Counted words in one JLPT section of the vocabulary summary.

    A None level means no JLPT listing, independently of vocabulary knowledge.
    These records contain data; the page template renders the bottom list.
    """

    jlpt_level: int | None
    word_counts: tuple[VocabularyCount, ...]


def normalize_identity(value: str) -> str:
    """Normalize Unicode and compare kana identities in hiragana."""
    return _to_hiragana(unicodedata.normalize("NFKC", value).strip())


_parser_state = local()


def _get_reader_tokenizer() -> tokenizer.Tokenizer:
    """Reuse a tokenizer without sharing writable scratch memory across threads.

    Sudachi updates internal buffers during tokenization. Each request thread
    gets its own instance so concurrent requests do not overwrite that state.
    """
    if not hasattr(_parser_state, "tokenizer"):
        _parser_state.tokenizer = dictionary.Dictionary(dict="core").create()
    return _parser_state.tokenizer


def _iter_article_morphemes(
    text: str,
) -> Iterator[tuple[morpheme.Morpheme, int]]:
    """Yield native tokens and chunk offsets within Sudachi's ~49KB input limit.

    Batch near sentence/newline boundaries to avoid a parser call per sentence.
    Offsets are local to a chunk; the yielded start offset maps them to the article.
    Sentence-by-sentence parsing would work too, but a single long sentence can
    still exceed the byte limit and needs this size guard.

    Hard split unpunctuated passages at 12,000 code points (at most 48,000 UTF-8
    bytes). Normalization can expand text, so shrink oversized chunks further.
    """
    parser = _get_reader_tokenizer()
    start = 0
    while start < len(text):
        end = min(start + 12_000, len(text))
        if end < len(text):
            boundary = max(text.rfind(mark, start, end) for mark in "\n。！？!?")
            if boundary >= start:
                end = boundary + 1
        while True:
            try:
                tokens = parser.tokenize(
                    text[start:end], tokenizer.Tokenizer.SplitMode.C
                )
                break
            except SudachiError as error:
                if "Input is too long" not in str(error) or end - start <= 1:
                    raise
                end = start + (end - start) // 2
        for token in tokens:
            yield token, start
        start = end


def token_identities(token: morpheme.Morpheme) -> tuple[str, ...]:
    """Return dictionary and surface identities without reading homophone matches."""
    candidates = (token.dictionary_form(), token.surface())
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
    normalized_known_words = {normalize_identity(word) for word in known_words}
    jlpt_index = _normalized_jlpt_index()
    tokens: list[ArticleToken] = []
    previous_end = 0
    whitespace = ""
    for token, offset in _iter_article_morphemes(normalized_text):
        start, end = offset + token.begin(), offset + token.end()
        surface = normalized_text[start:end]
        whitespace += normalized_text[previous_end:start]
        previous_end = end
        part_of_speech = PartOfSpeech(*token.part_of_speech())
        if part_of_speech.category == "空白":
            whitespace += surface
            continue
        identities = token_identities(token)
        name_kind = (
            {"人名": "person", "地名": "place"}.get(part_of_speech.subclass)
            if part_of_speech.category == "名詞"
            and part_of_speech.subcategory == "固有名詞"
            else None
        )
        jlpt_level = (
            None
            if name_kind or not _is_vocabulary(surface, part_of_speech)
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
                surface=surface,
                leading_whitespace=whitespace,
                reading=(
                    _to_hiragana(token.reading_form())
                    if token.reading_form() and not token.is_oov()
                    else None
                ),
                identities=identities,
                is_known=any(
                    identity in normalized_known_words for identity in identities
                ),
                jlpt_level=jlpt_level,
                part_of_speech=part_of_speech,
                name_kind=name_kind,
                start=start,
                end=end,
            )
        )
        whitespace = ""
    if suffix := whitespace + normalized_text[previous_end:]:
        tokens.append(ArticleToken("", suffix, None, (), False, None))
    return tokens


def build_unknown_vocabulary_summary(
    analyzed_tokens: list[ArticleToken],
) -> list[JlptVocabularyGroup]:
    """Filter unknown vocabulary, count dictionary forms, then build JLPT sections.

    Unknown means absent from the vocabulary inventory, not absent from JLPT data.
    Filter before counting: known words, kana-only tokens, names and grammatical
    tokens never enter the counts. 食べた and 食べます contribute to 食べる.
    Return N5–N1 then Unlisted, each sorted by descending occurrence count;
    equal counts retain first-appearance order. Input tokens are not modified.
    """
    counts_by_jlpt_level: dict[int | None, dict[str, int]] = {}
    for token in analyzed_tokens:
        if token.is_known or not token.identities or not token.is_vocabulary:
            continue
        dictionary_form = token.identities[0]
        counts_for_level = counts_by_jlpt_level.setdefault(token.jlpt_level, {})
        counts_for_level[dictionary_form] = counts_for_level.get(dictionary_form, 0) + 1

    vocabulary_groups: list[JlptVocabularyGroup] = []
    for jlpt_level in (5, 4, 3, 2, 1, None):
        counts_for_level = counts_by_jlpt_level.get(jlpt_level)
        if not counts_for_level:
            continue
        word_counts = [
            VocabularyCount(dictionary_form, occurrence_count)
            for dictionary_form, occurrence_count in counts_for_level.items()
        ]
        word_counts.sort(key=lambda word: word.occurrence_count, reverse=True)
        vocabulary_groups.append(
            JlptVocabularyGroup(jlpt_level=jlpt_level, word_counts=tuple(word_counts))
        )
    return vocabulary_groups

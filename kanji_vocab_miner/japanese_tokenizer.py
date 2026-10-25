"""UI-independent, source-preserving native Sudachi C-mode tokenization."""

from collections.abc import Iterator
from dataclasses import dataclass
from threading import local

from sudachipy import dictionary, tokenizer
from sudachipy.errors import SudachiError


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


@dataclass(frozen=True)
class JapaneseToken:
    """Native analysis with absolute code-point offsets into unmodified source.

    Readings are Sudachi's katakana, or None for missing/OOV readings. Consumers
    decide how to normalize identities, display whitespace and render readings.
    No parser objects or UI-specific knowledge are retained.
    """

    surface: str
    start: int
    end: int
    dictionary_form: str
    reading: str | None
    part_of_speech: PartOfSpeech


_parser_state = local()


def _get_tokenizer() -> tokenizer.Tokenizer:
    """Reuse a parser per thread without sharing its writable scratch buffers."""
    if not hasattr(_parser_state, "tokenizer"):
        _parser_state.tokenizer = dictionary.Dictionary(dict="core").create()
    return _parser_state.tokenizer


def tokenize_japanese(text: str) -> Iterator[JapaneseToken]:
    """Yield native C-mode tokens without normalizing or filtering source text.

    Batch near sentence/newline boundaries within Sudachi's ~49KB input limit.
    Hard split unpunctuated passages at 12,000 code points (at most 48,000 UTF-8
    bytes). Normalization expansion may require smaller retries. Hard splits can
    change boundaries/readings at chunk edges, but never drop source characters.
    """
    parser = _get_tokenizer()
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
            token_start, token_end = start + token.begin(), start + token.end()
            yield JapaneseToken(
                surface=text[token_start:token_end],
                start=token_start,
                end=token_end,
                dictionary_form=token.dictionary_form(),
                reading=(token.reading_form() or None) if not token.is_oov() else None,
                part_of_speech=PartOfSpeech(*token.part_of_speech()),
            )
        start = end

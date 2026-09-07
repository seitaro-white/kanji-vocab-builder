"""Context-aware furigana rendering for Japanese definition cues."""

import re
from functools import lru_cache
from html import escape
from typing import List, Set

from fugashi import Tagger, UnidicNode

_KANJI_RE = re.compile(r"[\u4e00-\u9fff]")
_TOKEN_CHUNK_RE = re.compile(r"[\u4e00-\u9fff]+|[^\u4e00-\u9fff]+")
_KANA_RE = re.compile(r"^[\u3040-\u30ffー]+$")


@lru_cache(maxsize=1)
def _get_tagger() -> Tagger:
    """Return one lazily initialized tokenizer instance."""
    return Tagger()


def _to_hiragana(text: str) -> str:
    """Convert ordinary katakana reading characters to hiragana."""
    return "".join(
        chr(ord(character) - 0x60)
        if "ァ" <= character <= "ヶ"
        else character
        for character in text
    )


def _ruby(base: str, reading: str, reviewed_kanji: Set[str]) -> str:
    kanji = _KANJI_RE.findall(base)
    css_class = ' class="known"' if kanji and all(
        character in reviewed_kanji for character in kanji
    ) else ""
    return f"<ruby>{escape(base)}<rt{css_class}>{escape(reading)}</rt></ruby>"


def _render_aligned_token(
    surface: str, reading: str, reviewed_kanji: Set[str]
) -> str | None:
    """Align kanji chunks when surrounding kana makes each split unambiguous."""

    chunks = _TOKEN_CHUNK_RE.findall(surface)
    if any(
        not _KANJI_RE.fullmatch(chunk) and not _KANA_RE.fullmatch(chunk)
        for chunk in chunks
    ):
        return None

    rendered: List[str] = []
    reading_position = 0
    for index, chunk in enumerate(chunks):
        if not _KANJI_RE.fullmatch(chunk):
            kana = _to_hiragana(chunk)
            if not reading.startswith(kana, reading_position):
                return None
            rendered.append(escape(chunk))
            reading_position += len(kana)
            continue

        next_kana = chunks[index + 1] if index + 1 < len(chunks) else None
        if next_kana is None:
            chunk_reading = reading[reading_position:]
            reading_position = len(reading)
        else:
            anchor = _to_hiragana(next_kana)
            anchor_position = reading.find(anchor, reading_position)
            if anchor_position <= reading_position:
                return None
            chunk_reading = reading[reading_position:anchor_position]
            reading_position = anchor_position

        if not chunk_reading:
            return None
        rendered.append(_ruby(chunk, chunk_reading, reviewed_kanji))

    return "".join(rendered) if reading_position == len(reading) else None


def _render_token(token: UnidicNode, reviewed_kanji: Set[str]) -> str:
    """Render one Fugashi token as escaped text or owned ruby HTML."""
    surface = str(token)
    leading_space = escape(token.white_space)

    if not _KANJI_RE.search(surface):
        return leading_space + escape(surface)

    raw_reading = token.feature.kana
    # UniDic uses "*" as a sentinel when a feature has no dictionary value.
    # Unknown kanji are therefore preserved rather than given a guessed reading.
    if not raw_reading or raw_reading == "*":
        return leading_space + escape(surface)

    reading = _to_hiragana(raw_reading)
    aligned = _render_aligned_token(surface, reading, reviewed_kanji)
    return leading_space + (
        aligned if aligned is not None else _ruby(surface, reading, reviewed_kanji)
    )


def render_japanese_cue(senses: List[str], reviewed_kanji: Set[str]) -> str:
    """Return escaped ruby HTML with one visual block per Japanese sense."""
    tagger = _get_tagger()
    rendered_senses: List[str] = []
    for sense in senses:
        tokens = list(tagger(sense))
        content = "".join(
            _render_token(token, reviewed_kanji) for token in tokens
        )
        consumed_length = sum(
            len(token.white_space) + len(str(token)) for token in tokens
        )
        content += escape(sense[consumed_length:])
        rendered_senses.append(f'<div class="sense">{content}</div>')
    return "".join(rendered_senses)


def update_furigana_visibility(
    html: str, reviewed_kanji: Set[str]
) -> tuple[str, bool]:
    """Update known-reading classes on single or grouped ruby elements."""

    def update_ruby(match: re.Match[str]) -> str:
        base, attributes, reading = match.groups()
        represented_kanji = _KANJI_RE.findall(base)
        if not represented_kanji:
            return match.group(0)

        has_known_class = bool(
            re.search(r"\bclass=(?:\"known\"|'known')", attributes)
        )
        should_be_known = all(
            character in reviewed_kanji for character in represented_kanji
        )
        if has_known_class == should_be_known:
            return match.group(0)

        attributes = re.sub(
            r"\s*\bclass=(?:\"known\"|'known')", "", attributes
        )
        if should_be_known:
            attributes += ' class="known"'
        return f"<ruby>{base}<rt{attributes}>{reading}</rt></ruby>"

    updated = re.sub(
        r"<ruby>(.*?)<rt([^>]*)>(.*?)</rt></ruby>",
        update_ruby,
        html,
        flags=re.DOTALL,
    )
    return updated, updated != html

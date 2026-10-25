"""Context-aware furigana rendering for Japanese definition cues."""

import re
from html import escape
from typing import List, Set

from kanji_vocab_miner.japanese_tokenizer import tokenize_japanese

_KANJI_RANGE = (
    r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\U00020000-\U0002fa1f\U00030000-\U000323af"
)
_KANJI_RE = re.compile(f"[{_KANJI_RANGE}]")
_TOKEN_CHUNK_RE = re.compile(f"[{_KANJI_RANGE}]+|[^{_KANJI_RANGE}]+")
_KANA_RE = re.compile(r"^[\u3040-\u30ffー]+$")


def _to_hiragana(text: str) -> str:
    """Convert ordinary katakana reading characters to hiragana."""
    return "".join(
        chr(ord(character) - 0x60)
        if "ァ" <= character <= "ヶ"
        else character
        for character in text
    )


def _ruby(
    base: str, reading: str, reviewed_kanji: Set[str], known_class: str = "known"
) -> str:
    kanji = _KANJI_RE.findall(base)
    css_class = f' class="{escape(known_class, quote=True)}"' if kanji and all(
        character in reviewed_kanji for character in kanji
    ) else ""
    return f"<ruby>{escape(base)}<rt{css_class}>{escape(reading)}</rt></ruby>"


def _render_aligned_token(
    surface: str, reading: str, reviewed_kanji: Set[str], known_class: str = "known"
) -> str | None:
    """Align kanji chunks when surrounding kana makes each split unambiguous."""

    chunks = _TOKEN_CHUNK_RE.findall(surface)
    if any(
        not _KANJI_RE.search(chunk) and not _KANA_RE.fullmatch(chunk)
        for chunk in chunks
    ):
        return None

    rendered: List[str] = []
    reading_position = 0
    for index, chunk in enumerate(chunks):
        if not _KANJI_RE.search(chunk):
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
            if anchor_position <= reading_position or reading.find(
                anchor, anchor_position + 1
            ) != -1:
                return None
            chunk_reading = reading[reading_position:anchor_position]
            reading_position = anchor_position

        if not chunk_reading:
            return None
        rendered.append(_ruby(chunk, chunk_reading, reviewed_kanji, known_class))

    return "".join(rendered) if reading_position == len(reading) else None


def render_token_furigana(
    surface: str,
    reading: str | None,
    reviewed_kanji: Set[str] | None = None,
    *,
    known_class: str = "known",
) -> str:
    """Render one surface with aligned ruby, falling back to whole-token ruby."""
    reviewed_kanji = reviewed_kanji or set()
    if not _KANJI_RE.search(surface) or not reading or reading == "*":
        return escape(surface)

    normalized_reading = _to_hiragana(reading)
    aligned = _render_aligned_token(
        surface, normalized_reading, reviewed_kanji, known_class
    )
    return aligned or _ruby(surface, normalized_reading, reviewed_kanji, known_class)


def render_japanese_cue(senses: List[str], reviewed_kanji: Set[str]) -> str:
    """Render native C-mode ruby per sense, preserving unnormalized source text."""
    rendered_senses: List[str] = []
    for sense in senses:
        fragments: List[str] = []
        previous_end = 0
        for token in tokenize_japanese(sense):
            fragments.append(escape(sense[previous_end:token.start]))
            fragments.append(
                render_token_furigana(token.surface, token.reading, reviewed_kanji)
            )
            previous_end = token.end
        fragments.append(escape(sense[previous_end:]))
        content = "".join(fragments)
        rendered_senses.append(f'<div class="sense">{content}</div>')
    return "<br>".join(rendered_senses)


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

"""JLPT N5-N1 vocabulary level lookups, built from the embedded community list.

See jlpt_data.py for provenance and caveats (unofficial, not exhaustive).
"""

import functools

from pydantic import BaseModel

from kanji_vocab_miner.jlpt_data import WORDS

NUM_LEVELS = 5  # N5 (easiest) .. N1 (hardest)

# Shared N-level -> colour palette (hex, usable as-is by both Rich and
# prompt_toolkit styles). 0 is the "no level" fallback.
LEVEL_COLORS: dict[int, str] = {
    5: "#209c05",
    4: "#85e62c",
    3: "#ebff0a",
    2: "#f2ce02",
    1: "#ff0a0a",
    0: "#c3c4c7",
}


def level_label(level: int | None) -> str:
    """Human-readable label for a level, e.g. 5 -> 'N5'. Blank for None/0."""
    if not level:
        return ""
    return f"N{level}"


def parse_level(raw: str) -> int | None:
    """Parse a level argument like 'N5', 'n5', or '5' into 1-5, or None if invalid."""
    text = raw.strip().upper().removeprefix("N")
    if not text.isdigit():
        return None
    level = int(text)
    return level if 1 <= level <= NUM_LEVELS else None


class LevelWord(BaseModel):
    # A pydantic model (not a plain dataclass) so it survives InquirerPy's
    # internal `dataclasses.asdict()` round-trip unchanged when used as a
    # Choice value -- asdict() recursively flattens nested dataclasses into
    # plain dicts, but leaves other object types (like JishoWord, also
    # pydantic) alone.
    expression: str
    kana: str
    definition: str


@functools.lru_cache(maxsize=1)
def get_level_index() -> dict[str, int]:
    """Cached surface-form -> N-level index (1-5)."""
    return build_level_index()


def build_level_index() -> dict[str, int]:
    """Map every expression and kana reading in WORDS to its N-level."""
    index: dict[str, int] = {}
    for expression, kana, _definition, level in WORDS:
        index[expression] = level
        if kana and kana not in index:
            index[kana] = level
    return index


def words_in_level(level: int) -> list[LevelWord]:
    """Return the vendored entries tagged at the given N-level (1-5)."""
    if not (1 <= level <= NUM_LEVELS):
        return []
    return [
        LevelWord(expression=expression, kana=kana, definition=definition)
        for expression, kana, definition, word_level in WORDS
        if word_level == level
    ]

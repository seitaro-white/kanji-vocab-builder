"""JLPT N5-N1 kanji level lookups, built from the embedded community dataset.

See jlpt_kanji_data.py for provenance and caveats. Level formatting/parsing
(N5..N1) is shared with the vocabulary side in jlpt.py.
"""

import functools

from kanji_vocab_miner.jlpt import NUM_LEVELS
from kanji_vocab_miner.jlpt_kanji_data import LEVELS
from kanji_vocab_miner.utils import is_kanji


@functools.lru_cache(maxsize=1)
def get_kanji_level_index() -> dict[str, int]:
    """Cached kanji -> N-level index (1-5)."""
    return dict(LEVELS)


@functools.lru_cache(maxsize=1)
def kanji_level_totals() -> dict[int, int]:
    """Total jouyou kanji per N-level among those the source could place."""
    totals = {level: 0 for level in range(1, NUM_LEVELS + 1)}
    for level in LEVELS.values():
        totals[level] += 1
    return totals


def hardest_kanji(expression: str) -> tuple[str | None, int | None]:
    """Return the (kanji, N-level) of the most difficult kanji in `expression`.

    "Most difficult" means the lowest N-number (N1 is harder than N5). Returns
    (None, None) if the expression has no kanji at all. If it has kanji but
    none are in the level index, returns the first kanji found with a None
    level, so callers can still surface it rather than treat the word as
    kanji-free.
    """
    kanji_chars = [ch for ch in expression if is_kanji(ch)]
    if not kanji_chars:
        return None, None

    index = get_kanji_level_index()
    ranked = [(ch, index[ch]) for ch in kanji_chars if ch in index]
    if not ranked:
        return kanji_chars[0], None

    return min(ranked, key=lambda pair: pair[1])

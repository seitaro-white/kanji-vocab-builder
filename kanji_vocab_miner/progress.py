"""Pure progress-calculation logic (no IO), in the spirit of card_processor."""

from dataclasses import dataclass

from kanji_vocab_miner import jlpt, kanji_jlpt
from kanji_vocab_miner.jouyou_data import JOUYOU

# N5 (easiest) first, N1 (hardest) last.
LEVEL_ORDER: list[int] = [5, 4, 3, 2, 1]


@dataclass
class LevelBar:
    level: int  # JLPT N-level, 1-5
    known: int  # distinct known items (kanji or words) at this level
    total: int  # vendored items at this level


@dataclass
class VocabProgress:
    levels: list[LevelBar]  # one bar per N-level, N5..N1
    placed: int  # distinct deck words with a known level (sum of bar.known)
    total_ranked: int  # total vendored JLPT words
    unranked: int  # no JLPT level found for this deck word
    total_deck: int


@dataclass
class KanjiProgress:
    levels: list[LevelBar]  # one bar per N-level, N5..N1
    known_total: int
    total: int
    missing_from_deck: int
    unranked: int  # known jouyou kanji with no JLPT level in the source data


def kanji_coverage(reviewed_kanji: set[str], all_deck_kanji: set[str]) -> KanjiProgress:
    """Compute Jouyou kanji coverage from reviewed and deck-present kanji."""
    known = reviewed_kanji & JOUYOU
    level_index = kanji_jlpt.get_kanji_level_index()
    totals = kanji_jlpt.kanji_level_totals()

    unranked = 0
    known_counts = {level: 0 for level in LEVEL_ORDER}
    for kanji in known:
        level = level_index.get(kanji)
        if level is None:
            unranked += 1
            continue
        known_counts[level] += 1

    levels = [
        LevelBar(level=level, known=known_counts[level], total=totals[level])
        for level in LEVEL_ORDER
    ]

    return KanjiProgress(
        levels=levels,
        known_total=len(known),
        total=len(JOUYOU),
        missing_from_deck=len(JOUYOU - all_deck_kanji),
        unranked=unranked,
    )


def vocab_coverage(deck_words: list[str]) -> VocabProgress:
    """Compute JLPT-level coverage for the words present in the vocab deck.

    Each distinct deck word is placed via an exact lookup in the embedded
    JLPT index into its N-level; words absent from the index are `unranked`.
    """
    distinct = set(deck_words)
    level_index = jlpt.get_level_index()
    totals = jlpt.level_totals()

    unranked = 0
    known_counts = {level: 0 for level in LEVEL_ORDER}
    for word in distinct:
        level = level_index.get(word)
        if level is None:
            unranked += 1
            continue
        known_counts[level] += 1

    levels = [
        LevelBar(level=level, known=known_counts[level], total=totals[level])
        for level in LEVEL_ORDER
    ]
    return VocabProgress(
        levels=levels,
        placed=sum(known_counts.values()),
        total_ranked=sum(totals.values()),
        unranked=unranked,
        total_deck=len(distinct),
    )

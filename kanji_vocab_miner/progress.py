"""Pure progress-calculation logic (no IO), in the spirit of card_processor."""

from dataclasses import dataclass

from kanji_vocab_miner import jlpt, kanji_jlpt
from kanji_vocab_miner.jouyou_data import JOUYOU

# N5 (easiest) first, N1 (hardest) last.
LEVEL_ORDER: list[int] = [5, 4, 3, 2, 1]
# The current kanji study goal is JLPT N2 and everything below it.
KANJI_TARGET_LEVELS: list[int] = [5, 4, 3, 2]

# Manually tracked textbook progress. Values are the section totals.
READING_MAXIMA: dict[str, int] = {
    "reading_i": 41,
    "reading_ii": 29,
    "reading_iii": 11,
}
GRAMMAR_MAXIMA: dict[str, int] = {
    "grammar_i": 10,
    "grammar_ii": 11,
    "grammar_iii": 5,
}
READING_TOTAL = sum(READING_MAXIMA.values())
GRAMMAR_TOTAL = sum(GRAMMAR_MAXIMA.values())


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
    levels: list[LevelBar]  # detail bars for every N-level, N5..N1
    known_total: int  # reviewed kanji within the N2 target
    total: int  # all kanji within the N2 target
    missing_from_deck: int  # target kanji not present in the kanji deck
    unranked: int  # reviewed jouyou kanji with no JLPT level in the source data


@dataclass(frozen=True)
class ManualProgressCounts:
    """Completed section counts read from the manual progress file."""

    reading_i: int = 0
    reading_ii: int = 0
    reading_iii: int = 0
    grammar_i: int = 0
    grammar_ii: int = 0
    grammar_iii: int = 0


@dataclass(frozen=True)
class ManualProgressBar:
    """A labelled bar for a manually tracked textbook section."""

    label: str
    known: int
    total: int


@dataclass(frozen=True)
class ManualProgress:
    """Aggregated and per-part Reading and Grammar progress.

    Each tuple contains the aggregate bar first, followed by I, II, and III
    detail bars.  Keeping the display order in the calculation result makes
    the dashboard deterministic while leaving rendering concerns in render.py.
    """

    reading: tuple[ManualProgressBar, ...]
    grammar: tuple[ManualProgressBar, ...]


def manual_coverage(counts: ManualProgressCounts) -> ManualProgress:
    """Calculate aggregate and detail bars for manual textbook progress.

    The six section counts are independent: aggregate values are calculated
    from the sections and are not treated as an additional input.
    """
    reading = (
        ManualProgressBar(
            label="Total",
            known=sum(getattr(counts, key) for key in READING_MAXIMA),
            total=READING_TOTAL,
        ),
        ManualProgressBar("I", counts.reading_i, READING_MAXIMA["reading_i"]),
        ManualProgressBar("II", counts.reading_ii, READING_MAXIMA["reading_ii"]),
        ManualProgressBar("III", counts.reading_iii, READING_MAXIMA["reading_iii"]),
    )
    grammar = (
        ManualProgressBar(
            label="Total",
            known=sum(getattr(counts, key) for key in GRAMMAR_MAXIMA),
            total=GRAMMAR_TOTAL,
        ),
        ManualProgressBar("I", counts.grammar_i, GRAMMAR_MAXIMA["grammar_i"]),
        ManualProgressBar("II", counts.grammar_ii, GRAMMAR_MAXIMA["grammar_ii"]),
        ManualProgressBar(
            "III", counts.grammar_iii, GRAMMAR_MAXIMA["grammar_iii"]
        ),
    )
    return ManualProgress(reading=reading, grammar=grammar)


def kanji_coverage(reviewed_kanji: set[str], all_deck_kanji: set[str]) -> KanjiProgress:
    """Compute kanji coverage for the N2-and-below study target."""
    reviewed_jouyou = reviewed_kanji & JOUYOU
    level_index = kanji_jlpt.get_kanji_level_index()
    totals = kanji_jlpt.kanji_level_totals()
    target_kanji = {
        kanji
        for kanji in JOUYOU
        if level_index.get(kanji) in KANJI_TARGET_LEVELS
    }

    unranked = 0
    known_counts = {level: 0 for level in LEVEL_ORDER}
    for kanji in reviewed_jouyou:
        level = level_index.get(kanji)
        if level is None:
            unranked += 1
        else:
            known_counts[level] += 1

    levels = [
        LevelBar(level=level, known=known_counts[level], total=totals[level])
        for level in LEVEL_ORDER
    ]

    return KanjiProgress(
        levels=levels,
        known_total=len(reviewed_jouyou & target_kanji),
        total=len(target_kanji),
        missing_from_deck=len(target_kanji - all_deck_kanji),
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

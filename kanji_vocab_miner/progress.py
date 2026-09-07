"""Pure progress-calculation logic (no IO), in the spirit of card_processor."""

from dataclasses import dataclass
from datetime import date

from kanji_vocab_miner import kanji_jlpt
from kanji_vocab_miner.jouyou_data import JOUYOU

# The current kanji study goal is JLPT N2 and everything below it, easiest first.
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
VOCAB_TARGET = 6000


@dataclass
class LevelBar:
    level: int  # JLPT N-level, 1-5
    known: int  # reviewed kanji at this level
    total: int  # vendored kanji at this level


@dataclass(frozen=True)
class VocabProgress:
    """Vocabulary count relative to the core 6,000-word target."""

    known: int
    total: int


@dataclass
class KanjiProgress:
    levels: list[LevelBar]  # detail bars for target levels, N5..N2
    known_total: int  # reviewed kanji within the N2 target
    total: int  # all kanji within the N2 target
    missing_from_deck: int  # target kanji not present in the kanji deck
    unranked: int  # reviewed jouyou kanji with no JLPT level in the source data


@dataclass(frozen=True)
class ManualProgressCounts:
    """Manual vocabulary baseline and completed textbook section counts."""

    vocab_baseline: int
    vocab_tracking_start: date
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
    known_counts = {level: 0 for level in KANJI_TARGET_LEVELS}
    for kanji in reviewed_jouyou:
        level = level_index.get(kanji)
        if level is None:
            unranked += 1
        elif level in known_counts:
            known_counts[level] += 1

    levels = [
        LevelBar(level=level, known=known_counts[level], total=totals[level])
        for level in KANJI_TARGET_LEVELS
    ]

    return KanjiProgress(
        levels=levels,
        known_total=len(reviewed_jouyou & target_kanji),
        total=len(target_kanji),
        missing_from_deck=len(target_kanji - all_deck_kanji),
        unranked=unranked,
    )


def vocab_progress(baseline: int, added_since_baseline: int) -> VocabProgress:
    """Add newly created vocabulary notes to the manual baseline."""
    return VocabProgress(
        known=baseline + added_since_baseline,
        total=VOCAB_TARGET,
    )

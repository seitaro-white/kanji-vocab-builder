"""Pure progress-calculation logic (no IO), in the spirit of card_processor."""

from dataclasses import dataclass
from datetime import date

from kanji_vocab_miner import kanji_jlpt
from kanji_vocab_miner.jouyou_data import JOUYOU

# The current kanji study goal is JLPT N2 and everything below it, easiest first.
KANJI_TARGET_LEVELS: list[int] = [5, 4, 3, 2]

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
    reading_i_total: int
    reading_ii_total: int
    reading_iii_total: int
    grammar_i_total: int
    grammar_ii_total: int
    grammar_iii_total: int
    grammar_iv_total: int
    grammar_v_total: int
    grammar_vi_total: int
    reading_i: int = 0
    reading_ii: int = 0
    reading_iii: int = 0
    grammar_i: int = 0
    grammar_ii: int = 0
    grammar_iii: int = 0
    grammar_iv: int = 0
    grammar_v: int = 0
    grammar_vi: int = 0


@dataclass(frozen=True)
class ManualProgressBar:
    """A labelled bar for a manually tracked textbook section."""

    label: str
    known: int
    total: int


@dataclass(frozen=True)
class ManualProgress:
    """Aggregated and per-part Reading and Grammar progress.

    Each tuple contains the aggregate bar first, followed by section
    detail bars. Keeping the display order in the calculation result makes
    the dashboard deterministic while leaving rendering concerns in render.py.
    """

    reading: tuple[ManualProgressBar, ...]
    grammar: tuple[ManualProgressBar, ...]


def manual_coverage(counts: ManualProgressCounts) -> ManualProgress:
    """Calculate aggregate and detail bars for manual textbook progress.

    Section counts are independent: aggregate values are calculated from
    the sections and are not treated as an additional input.
    """
    reading = (
        ManualProgressBar(
            "Total",
            counts.reading_i + counts.reading_ii + counts.reading_iii,
            counts.reading_i_total + counts.reading_ii_total + counts.reading_iii_total,
        ),
        ManualProgressBar("I", counts.reading_i, counts.reading_i_total),
        ManualProgressBar("II", counts.reading_ii, counts.reading_ii_total),
        ManualProgressBar("III", counts.reading_iii, counts.reading_iii_total),
    )
    grammar = (
        ManualProgressBar(
            "Total",
            sum(
                (
                    counts.grammar_i,
                    counts.grammar_ii,
                    counts.grammar_iii,
                    counts.grammar_iv,
                    counts.grammar_v,
                    counts.grammar_vi,
                )
            ),
            sum(
                (
                    counts.grammar_i_total,
                    counts.grammar_ii_total,
                    counts.grammar_iii_total,
                    counts.grammar_iv_total,
                    counts.grammar_v_total,
                    counts.grammar_vi_total,
                )
            ),
        ),
        ManualProgressBar("I", counts.grammar_i, counts.grammar_i_total),
        ManualProgressBar("II", counts.grammar_ii, counts.grammar_ii_total),
        ManualProgressBar("III", counts.grammar_iii, counts.grammar_iii_total),
        ManualProgressBar("IV", counts.grammar_iv, counts.grammar_iv_total),
        ManualProgressBar("V", counts.grammar_v, counts.grammar_v_total),
        ManualProgressBar("VI", counts.grammar_vi, counts.grammar_vi_total),
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

"""Pure progress-calculation logic (no IO), in the spirit of card_processor."""

from collections.abc import Mapping
from dataclasses import dataclass

from kanji_vocab_miner.jouyou_data import BY_GRADE, JOUYOU

GRADE_ORDER: list[int | str] = [1, 2, 3, 4, 5, 6, "secondary"]


@dataclass
class GradeBar:
    grade: int | str
    known: int
    total: int


@dataclass
class BandCell:
    band: int  # nf band number, 1-48
    known: int  # distinct deck words placed in this band
    size: int  # words per band (500)


@dataclass
class VocabProgress:
    bands: list[BandCell]  # one cell per nf band, 1..48
    placed: int  # distinct deck words that have a band (sum of cell.known)
    total_ranked: int  # 48 * 500 == 24000
    unranked: int  # no nf band found (rare word or no exact dictionary match)
    total_deck: int


# JMdict nf priority bands: 48 bands of 500 words each -> the top 24,000 words.
BAND_SIZE = 500
NUM_BANDS = 48

# Display bins (label, first nf band, last nf band; both inclusive, 1-indexed).
# Narrow (500-wide) up front where coverage is concentrated, widening out, with
# a single wide tail bin. Snapped to nf-band (500-word) boundaries.
VOCAB_BINS: list[tuple[str, int, int]] = [
    ("0-500", 1, 1),
    ("500-1k", 2, 2),
    ("1-1.5k", 3, 3),
    ("1.5-2k", 4, 4),
    ("2-2.5k", 5, 5),
    ("2.5-3.5k", 6, 7),
    ("3.5-4.5k", 8, 9),
    ("4.5-5.5k", 10, 11),
    ("5.5k+", 12, NUM_BANDS),
]


@dataclass
class KanjiProgress:
    grades: list[GradeBar]
    known_total: int
    total: int
    missing_from_deck: int


def kanji_coverage(reviewed_kanji: set[str], all_deck_kanji: set[str]) -> KanjiProgress:
    """Compute Jouyou kanji coverage from reviewed and deck-present kanji."""
    known = reviewed_kanji & JOUYOU

    grades = []
    for grade in GRADE_ORDER:
        grade_set = set(BY_GRADE[grade])
        grades.append(
            GradeBar(
                grade=grade,
                known=len(reviewed_kanji & grade_set),
                total=len(grade_set),
            )
        )

    return KanjiProgress(
        grades=grades,
        known_total=len(known),
        total=len(JOUYOU),
        missing_from_deck=len(JOUYOU - all_deck_kanji),
    )


def binned_vocab(
    bands: list[BandCell], bins: list[tuple[str, int, int]] = VOCAB_BINS
) -> list[tuple[str, int, int]]:
    """Collapse per-band cells into display bins of (label, known, total)."""
    by_band = {cell.band: cell for cell in bands}
    out: list[tuple[str, int, int]] = []
    for label, lo, hi in bins:
        chunk = [by_band[n] for n in range(lo, hi + 1) if n in by_band]
        known = sum(c.known for c in chunk)
        total = sum(c.size for c in chunk)
        out.append((label, known, total))
    return out


def vocab_coverage(
    deck_words: list[str], freq_map: Mapping[str, int]
) -> VocabProgress:
    """Compute frequency-tier coverage for the words present in the vocab deck.

    `freq_map` maps a surface form to its nf band (1-48). Each distinct deck
    word is placed via an exact lookup in that map into its band; words absent
    from the map are `unranked`.
    """
    distinct = set(deck_words)

    unranked = 0
    band_counts = [0] * NUM_BANDS  # index 0 == band 1
    for word in distinct:
        band = freq_map.get(word)
        if band is None or not (1 <= band <= NUM_BANDS):
            unranked += 1
            continue
        band_counts[band - 1] += 1

    bands = [
        BandCell(band=i + 1, known=band_counts[i], size=BAND_SIZE)
        for i in range(NUM_BANDS)
    ]
    return VocabProgress(
        bands=bands,
        placed=sum(band_counts),
        total_ranked=NUM_BANDS * BAND_SIZE,
        unranked=unranked,
        total_deck=len(distinct),
    )

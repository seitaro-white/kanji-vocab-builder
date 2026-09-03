"""Create a banded vocabulary-testing export for Google Sheets."""

# %%
# Imports

from functools import lru_cache
import re

from jamdict import Jamdict
import pandas as pd

from kanji_vocab_miner.kanji_jlpt import get_kanji_level_index


# %%
# Configuration

INPUT_PATH = "data/Optimized Kore 6k - Sheet1.csv"
OUTPUT_PATH = "data/Optimized Kore 6k - testing sample.csv"
BAND_SIZE = 1000
SAMPLE_SIZE = 60
RANDOM_SEED = 42

KANJI_GROUP_PATTERN = re.compile(r"([\u4e00-\u9fff々]+)\[([^]]+)]")
KANJI_LEVELS = get_kanji_level_index()
jamdict = Jamdict()


def katakana_to_hiragana(text: str) -> str:
    """Convert ordinary katakana characters to hiragana."""
    return "".join(
        chr(ord(character) - 0x60)
        if "ァ" <= character <= "ヶ"
        else character
        for character in text
    )


@lru_cache(maxsize=None)
def get_kanji_readings(kanji: str) -> tuple[str, ...]:
    """Return Japanese KANJIDIC readings for one kanji."""
    result = jamdict.lookup(kanji)
    character = next(
        (item for item in result.chars if item.literal == kanji),
        None,
    )
    if character is None:
        return ()

    readings: set[str] = set()
    for group in character.rm_groups:
        for reading in group.readings:
            if reading.r_type not in {"ja_on", "ja_kun"}:
                continue

            normalized = katakana_to_hiragana(reading.value)
            readings.add(normalized.replace("-", ""))
            # KUN readings such as あつ.い use the part before the dot when
            # the okurigana is already visible in the expression.
            readings.add(normalized.split(".", maxsplit=1)[0].replace("-", ""))

    return tuple(reading for reading in readings if reading)


def reading_variants(reading: str) -> set[str]:
    """Return common compound-word variants of a dictionary reading."""
    variants = {reading}
    voiced_initials = {
        "か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
        "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
        "た": "だ", "ち": "ぢ", "つ": "づ", "て": "で", "と": "ど",
        "は": "ば", "ひ": "び", "ふ": "ぶ", "へ": "べ", "ほ": "ぼ",
    }
    if reading and reading[0] in voiced_initials:
        variants.add(voiced_initials[reading[0]] + reading[1:])

    # Common sound contraction in compounds, e.g. がく + こう -> がっこう.
    for variant in tuple(variants):
        if variant.endswith(("く", "き", "つ", "ち")):
            variants.add(variant[:-1] + "っ")

    return variants


def align_reading(kanji_group: str, reading: str) -> list[str] | None:
    """Split a group reading into one reading per kanji when possible."""
    candidates = [
        sorted(
            {
                variant
                for base_reading in get_kanji_readings(kanji)
                for variant in reading_variants(base_reading)
            },
            key=len,
            reverse=True,
        )
        for kanji in kanji_group
    ]

    @lru_cache(maxsize=None)
    def align(kanji_index: int, reading_index: int) -> tuple[str, ...] | None:
        if kanji_index == len(kanji_group):
            return () if reading_index == len(reading) else None

        for candidate in candidates[kanji_index]:
            if not reading.startswith(candidate, reading_index):
                continue
            remainder = align(kanji_index + 1, reading_index + len(candidate))
            if remainder is not None:
                return (reading[reading_index : reading_index + len(candidate)], *remainder)
        return None

    result = align(0, 0)
    return list(result) if result is not None else None


def annotate_difficult_kanji(furigana: str) -> str:
    """Keep readings only for N1 or unclassified kanji in an expression."""
    # Spaces in the source separate independently annotated kanji groups, so
    # keep them until after replacements are complete.
    source_furigana = str(furigana).strip()

    def replace_group(match: re.Match[str]) -> str:
        kanji_group, reading = match.groups()
        is_difficult = [KANJI_LEVELS.get(kanji) in {1, None} for kanji in kanji_group]
        if not any(is_difficult):
            return kanji_group

        aligned_readings = align_reading(kanji_group, reading)
        if aligned_readings is None:
            # Preserve useful furigana when an irregular reading cannot be
            # divided reliably between individual kanji.
            return f"{kanji_group}[{reading}]"

        return "".join(
            f"{kanji}[{kanji_reading}]" if difficult else kanji
            for kanji, kanji_reading, difficult in zip(
                kanji_group,
                aligned_readings,
                is_difficult,
            )
        )

    annotated = KANJI_GROUP_PATTERN.sub(replace_group, source_furigana)
    return "".join(annotated.split())


# %%
# Build the export

df = pd.read_csv(INPUT_PATH)
df = df.sort_values("Core-index").reset_index(drop=True)

df["Band"] = (df.index // BAND_SIZE) + 1
sample_indices = (
    df.groupby("Band", group_keys=False)
    .sample(n=SAMPLE_SIZE, random_state=RANDOM_SEED)
    .index
)
df["Sample"] = df.index.isin(sample_indices).astype(int)
df["N2-safe-expression"] = df["Vocab-furigana"].apply(annotate_difficult_kanji)

df.to_csv(OUTPUT_PATH, index=False)

# Keep the six DataFrames available when running this as an interactive script.
df_groups = [group.copy() for _, group in df.groupby("Band", sort=True)]

print(f"Wrote {len(df):,} rows to {OUTPUT_PATH}")
print(df.groupby("Band")["Sample"].sum().to_string())

# %%
# Smaller verison
df_for_copy[["Core-index", "Vocab-expression", "Vocab-kana", "Vocab-meaning", "N2-safe-expression", "Band", "Sample"]]
df_for_copy.to_clipboard()
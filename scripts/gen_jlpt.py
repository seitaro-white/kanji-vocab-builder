"""Regenerate kanji_vocab_miner/jlpt_data.py from a community JLPT word list.

The JLPT stopped publishing an official vocabulary list after the 2010 test
revision, so there is no authoritative N5-N1 word list. This pulls the
widely-used community list maintained at elzup/jlpt-word-list (MIT licensed),
which traces back to the tanos.co.uk level lists via jamsinclair's Anki decks.

Pinned to a specific commit for reproducibility.

Run with: uv run python scripts/gen_jlpt.py
"""

import csv
import io
import os
import urllib.request

COMMIT = "13aa3c54b27115be72d8a62cd4071077c68d2171"
RAW_URL = f"https://raw.githubusercontent.com/elzup/jlpt-word-list/{COMMIT}/src/n{{level}}.csv"

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "kanji_vocab_miner",
    "jlpt_data.py",
)


def fetch_level(level: int) -> list[tuple[str, str, str]]:
    """Return (expression, kana, meaning) rows for one N-level's CSV."""
    with urllib.request.urlopen(RAW_URL.format(level=level)) as resp:
        text = resp.read().decode("utf-8")
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        expression = row["expression"].strip()
        kana = row["reading"].strip()
        meaning = row["meaning"].strip()
        if expression:
            rows.append((expression, kana, meaning))
    return rows


def main() -> None:
    # A word can appear in more than one level's file (the source decks mix
    # old 4-level and new 5-level JLPT tagging). When that happens, keep the
    # easiest (highest N number) level -- the level most learners meet it at.
    by_expression: dict[str, tuple[str, str, int]] = {}
    for level in (5, 4, 3, 2, 1):
        for expression, kana, meaning in fetch_level(level):
            existing = by_expression.get(expression)
            if existing is None or level > existing[2]:
                by_expression[expression] = (kana, meaning, level)

    words = sorted(
        (expression, kana, meaning, level)
        for expression, (kana, meaning, level) in by_expression.items()
    )

    header = f'''"""Embedded JLPT N5-N1 vocabulary list.

Community-maintained data (MIT licensed), not an official JLPT publication --
the JLPT stopped releasing vocabulary lists after the 2010 test revision.
Sourced from github.com/elzup/jlpt-word-list at commit {COMMIT},
which traces back to the tanos.co.uk level lists.

Each entry is (expression, kana, meaning, level) where level is the N-number
(5 == N5/easiest .. 1 == N1/hardest). Words tagged at more than one level in
the source decks keep the easiest (highest N-number) level.

Regenerate with: uv run python scripts/gen_jlpt.py
"""

'''
    lines = [header, "WORDS: list[tuple[str, str, str, int]] = ["]
    for expression, kana, meaning, level in words:
        lines.append(f"    {(expression, kana, meaning, level)!r},")
    lines.append("]")
    lines.append("")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUT_PATH} ({len(words)} words)")


if __name__ == "__main__":
    main()

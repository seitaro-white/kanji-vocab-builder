"""Regenerate kanji_vocab_miner/jlpt_kanji_data.py from a community JLPT kanji list.

Like the vocabulary list (see gen_jlpt.py), the JLPT itself has never published
an official N5-N1 kanji list. This pulls davidluzgouveia/kanji-data (MIT
licensed), which derives its `jlpt_new` (post-2010, 5-level) field from
Jonathan Waller's JLPT Resources page (tanos.co.uk) -- the same lineage as the
vocabulary list.

Pinned to a specific commit for reproducibility.

Run with: uv run python scripts/gen_jlpt_kanji.py
"""

import json
import os
import urllib.request

COMMIT = "00fd7079c3890f430759536f91aa5e854ec0ca4f"
RAW_URL = f"https://raw.githubusercontent.com/davidluzgouveia/kanji-data/{COMMIT}/kanji-jouyou.json"

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "kanji_vocab_miner",
    "jlpt_kanji_data.py",
)


def main() -> None:
    with urllib.request.urlopen(RAW_URL) as resp:
        data = json.load(resp)

    # Only the jouyou kanji that the source could actually place on the
    # modern (post-2010) N5-N1 scale; the rest are left untagged.
    levels = {
        kanji: entry["jlpt_new"]
        for kanji, entry in data.items()
        if entry.get("jlpt_new") is not None
    }

    header = f'''"""Embedded JLPT N5-N1 kanji list (jouyou kanji only).

Community-maintained data (MIT licensed), not an official JLPT publication --
the JLPT has never published an official kanji-by-level list. Sourced from
github.com/davidluzgouveia/kanji-data at commit {COMMIT} (its
`jlpt_new` field), which traces back to the tanos.co.uk level lists.

Maps each kanji to its N-number (5 == N5/easiest .. 1 == N1/hardest). Jouyou
kanji the source could not place on the modern 5-level scale are omitted.

Regenerate with: uv run python scripts/gen_jlpt_kanji.py
"""

'''
    lines = [header, "LEVELS: dict[str, int] = {"]
    for kanji in sorted(levels):
        lines.append(f"    {kanji!r}: {levels[kanji]!r},")
    lines.append("}")
    lines.append("")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUT_PATH} ({len(levels)} kanji)")


if __name__ == "__main__":
    main()

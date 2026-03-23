#!/usr/bin/env python3
"""
One-time patch script to migrate legacy vocab cards to the standard format.

Legacy formats detected:
  1. Plain text: "人口(じんこう)" — kanji + parenthesized reading, no HTML
  2. Old Jisho HTML: contains <span class="furigana"> / <span class="text"> markup

After patching, cards are left in Anki-notation format (漢[かん]字[じ]) so that
the existing sync-furigana command can convert them to ruby HTML in one pass.

Usage:
    uv run python patch_legacy_cards.py           # live mode
    uv run python patch_legacy_cards.py --dry-run  # preview only
"""

import argparse
import re
import sys
import urllib.parse
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from kanji_vocab_miner.anki.connect import send_request, update_note, sync_vocab_furigana
from kanji_vocab_miner.config import VOCAB_DECK_NAME, FIELDS
from kanji_vocab_miner.jisho import fetch_jisho_word_furigana, JishoWord

# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

_PLAIN_TEXT_RE = re.compile(
    r"^([\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\uF900-\uFAFF]+)"
    r"\s*\(([\u3040-\u309F\u30A0-\u30FF]+)\)$"
)


_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def detect_plain_text(front: str) -> Optional[Tuple[str, str]]:
    """Detect plain-text format (kanji + parenthesized reading, optional whitespace/newline/<br> between)."""
    text = _BR_RE.sub("\n", front).strip()
    if "<" in text:
        return None
    m = _PLAIN_TEXT_RE.match(text)
    return (m.group(1), m.group(2)) if m else None


def detect_jisho_html(front: str) -> Optional[str]:
    """Detect old Jisho-copied HTML. Returns plain expression or None."""
    if 'class="furigana"' not in front and 'class="text"' not in front:
        return None
    soup = BeautifulSoup(front, "html.parser")
    text_span = soup.select_one("span.text")
    if text_span:
        return text_span.get_text(strip=True)
    return None


# ---------------------------------------------------------------------------
# Jisho lookup
# ---------------------------------------------------------------------------

def lookup_jisho_word(expression: str) -> Optional[JishoWord]:
    """Return a JishoWord for the given expression, or None if not found."""
    encoded = urllib.parse.quote(expression)
    urls = [
        f"https://jisho.org/api/v1/search/words?keyword={encoded}",
        f"https://jisho.org/api/v1/search/words?keyword=*{encoded}*",
    ]

    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception:
            continue

        for item in data:
            japanese = item.get("japanese", [])
            if not japanese:
                continue
            word = japanese[0].get("word", japanese[0].get("reading", ""))
            reading = japanese[0].get("reading", "")
            if word != expression:
                continue

            jlpt_level = 0
            for level in item.get("jlpt", []):
                if level.startswith("jlpt-n"):
                    try:
                        jlpt_level = int(level.split("jlpt-n")[1])
                        break
                    except (ValueError, IndexError):
                        pass

            definitions, parts_of_speech = [], []
            for sense in item.get("senses", [])[:3]:
                definitions.append("; ".join(sense.get("english_definitions", [])))
                parts_of_speech.append("; ".join(sense.get("parts_of_speech", [])))

            if not definitions:
                continue

            return JishoWord(
                expression=word,
                kana=reading,
                jlpt=jlpt_level,
                definitions=definitions,
                parts_of_speech=parts_of_speech,
            )

    return None


# ---------------------------------------------------------------------------
# Field builder
# ---------------------------------------------------------------------------

def build_new_fields(word: JishoWord) -> dict:
    """Build the complete field dict for a standard card."""
    try:
        front = fetch_jisho_word_furigana(word.expression)
    except Exception:
        # Fallback: plain expression with full reading in brackets
        front = f"{word.expression}[{word.kana}]"

    return {
        FIELDS["front"]: front,
        FIELDS["back"]: word.definitions[0],
        FIELDS["expression"]: word.expression,
        FIELDS["kana_reading"]: word.kana,
        FIELDS["grammar"]: word.parts_of_speech[0] if word.parts_of_speech else "",
        FIELDS["definition"]: word.definitions[0],
        FIELDS["additional_definitions"]: "\n".join(word.definitions[1:]),
        FIELDS["jlpt"]: f"JLPT N{word.jlpt}" if word.jlpt else "",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy Anki vocab cards to the standard format."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to Anki",
    )
    args = parser.parse_args()
    dry_run: bool = args.dry_run

    if dry_run:
        print("=== DRY RUN — no changes will be written ===\n")

    # Fetch all cards from the vocab deck
    print(f"Fetching cards from: {VOCAB_DECK_NAME}")
    try:
        card_ids = send_request("findCards", query=f'deck:"{VOCAB_DECK_NAME}"')
    except Exception as e:
        print(f"Error connecting to Anki: {e}")
        sys.exit(1)

    if not card_ids:
        print("No cards found.")
        return

    print(f"Found {len(card_ids)} cards. Fetching card info...")
    cards_info = send_request("cardsInfo", cards=card_ids)

    # First pass: identify legacy cards (fast, no network calls)
    seen_notes: set = set()
    legacy: list = []
    for card in cards_info:
        note_id = card.get("note")
        if note_id in seen_notes:
            continue
        seen_notes.add(note_id)

        front = card.get("fields", {}).get("Front", {}).get("value", "")

        p1 = detect_plain_text(front)
        if p1:
            legacy.append((note_id, p1[0], "plain text"))
            continue

        p2 = detect_jisho_html(front)
        if p2:
            legacy.append((note_id, p2, "Jisho HTML"))

    total_notes = len(seen_notes)
    print(f"Scanned {total_notes} unique notes — {len(legacy)} legacy card(s) found.\n")

    if not legacy:
        print("Nothing to do.")
        return

    # Second pass: Jisho lookups + updates (slow, shown with progress bar)
    patched = 0
    failed = 0

    with tqdm(legacy, unit="card", desc="Patching") as bar:
        for note_id, expression, pattern_label in bar:
            bar.set_postfix_str(f"{expression} [{pattern_label}]")

            word = lookup_jisho_word(expression)
            if word is None:
                tqdm.write(f"  ✗ [{pattern_label}] '{expression}' — not found on Jisho, skipping")
                failed += 1
                continue

            new_fields = build_new_fields(word)

            if dry_run:
                tqdm.write(
                    f"  [DRY RUN] '{expression}' ({pattern_label}) → "
                    f"Front: {new_fields[FIELDS['front']]} | "
                    f"Back: {new_fields[FIELDS['back']]} | "
                    f"Kana: {new_fields[FIELDS['kana_reading']]} | "
                    f"JLPT: {new_fields[FIELDS['jlpt']]}"
                )
                patched += 1
            else:
                try:
                    update_note(note_id, new_fields)
                    tqdm.write(f"  ✓ [{pattern_label}] '{expression}' updated")
                    patched += 1
                except Exception as e:
                    tqdm.write(f"  ✗ [{pattern_label}] '{expression}' — update failed: {e}")
                    failed += 1

    # Run furigana sync to convert Anki notation → ruby HTML
    if not dry_run and patched > 0:
        print("\nConverting furigana notation to HTML (sync-furigana)...")
        converted = sync_vocab_furigana()
        print(f"  Converted {converted} card(s)")

    prefix = "DRY RUN " if dry_run else ""
    verb = "Would patch" if dry_run else "Patched"
    print(f"\n{prefix}Summary — {verb}: {patched}", end="")
    if failed:
        print(f"  |  Failed/skipped: {failed}", end="")
    print()


if __name__ == "__main__":
    main()

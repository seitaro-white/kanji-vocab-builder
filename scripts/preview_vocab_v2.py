"""Add two fixed V2 vocabulary notes for manual Anki template validation."""

from datetime import datetime
from typing import Any, Dict, List, Set

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.config import VOCAB_NOTE_TYPE_V2, VOCAB_V2_FIELDS
from kanji_vocab_miner.furigana import (
    render_japanese_cue,
    update_furigana_visibility,
)

PREVIEW_DECK = "KanjiVocabMiner-V2-Preview-DELETE-ME"
PREVIEW_TAG = "kanji-vocab-miner-v2-preview"


def _front_with_visibility(html: str, reviewed_kanji: Set[str]) -> str:
    return update_furigana_visibility(html, reviewed_kanji)[0]


def _sample_notes(reviewed_kanji: Set[str], run_tag: str) -> List[Dict[str, Any]]:
    samples = [
        {
            "expression": "学校",
            "kana": "がっこう",
            "front": "<ruby>学校<rt>がっこう</rt></ruby>",
            "definition": "school",
            "japanese_senses": ["児童・生徒などに教育を行う所。"],
            "recall": "",
            "url": "https://kotobank.jp/word/%E5%AD%A6%E6%A0%A1",
        },
        {
            "expression": "覚える",
            "kana": "おぼえる",
            "front": "<ruby>覚<rt>おぼ</rt></ruby>える",
            "definition": "to remember",
            "japanese_senses": ["経験したことを記憶にとどめる。"],
            "recall": "1",
            "url": "https://kotobank.jp/word/%E8%A6%9A%E3%81%88%E3%82%8B",
        },
    ]

    notes: List[Dict[str, Any]] = []
    for sample in samples:
        senses = sample["japanese_senses"]
        fields = {
            VOCAB_V2_FIELDS["front"]: _front_with_visibility(
                sample["front"], reviewed_kanji
            ),
            VOCAB_V2_FIELDS["back"]: sample["definition"],
            VOCAB_V2_FIELDS["expression"]: sample["expression"],
            VOCAB_V2_FIELDS["kana_reading"]: sample["kana"],
            VOCAB_V2_FIELDS["grammar"]: "",
            VOCAB_V2_FIELDS["definition"]: sample["definition"],
            VOCAB_V2_FIELDS["additional_definitions"]: "",
            VOCAB_V2_FIELDS["jlpt"]: "",
            VOCAB_V2_FIELDS["japanese_definition"]: "\n".join(senses),
            VOCAB_V2_FIELDS["japanese_cue"]: render_japanese_cue(
                senses, reviewed_kanji
            ),
            VOCAB_V2_FIELDS["recall"]: sample["recall"],
            VOCAB_V2_FIELDS["definition_source"]: "デジタル大辞泉",
            VOCAB_V2_FIELDS["definition_url"]: sample["url"],
        }
        notes.append(
            {
                "deckName": PREVIEW_DECK,
                "modelName": VOCAB_NOTE_TYPE_V2,
                "fields": fields,
                "tags": [PREVIEW_TAG, run_tag],
                "options": {"allowDuplicate": False},
            }
        )
    return notes


def main() -> None:
    """Create the preview deck and print manual validation and cleanup steps."""
    model_names = connect.send_request("modelNames")
    if VOCAB_NOTE_TYPE_V2 not in model_names:
        raise SystemExit(
            f"Missing note type '{VOCAB_NOTE_TYPE_V2}'. "
            "Run `uv run python scripts/install_vocab_v2.py` first."
        )

    connect.send_request("createDeck", deck=PREVIEW_DECK)
    reviewed_kanji = connect.get_reviewed_kanji()
    run_tag = f"{PREVIEW_TAG}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    note_ids: List[int] = []
    for note in _sample_notes(reviewed_kanji, run_tag):
        note_id = connect.send_request("addNote", note=note)
        note_ids.append(note_id)

    card_ids = connect.send_request(
        "findCards", query=" OR ".join(f"nid:{note_id}" for note_id in note_ids)
    )
    print(f"Created preview deck: {PREVIEW_DECK}")
    print(f"Run tag: {run_tag}")
    print(f"Note IDs: {note_ids}")
    print(f"Card IDs: {card_ids}")
    print(
        """
Manual checks:
1. 学校 initially has Recognition only; 覚える has Recognition and Recall.
2. Confirm Recognition looks and behaves like the existing Card 1.
3. Confirm Recall asks with the Japanese cue and reveals cue, target, reading,
   and the linked source without an English definition.
4. Confirm question-side readings hide for reviewed kanji and answers reveal all.
5. In Browse, set 学校's Recall field to 1 and confirm a Recall card appears.
6. Clear that Recall field, then run Tools → Empty Cards and confirm removal.

Cleanup (nothing is deleted automatically):
- Browse for the printed run tag and delete those two notes, or
- delete the deck "KanjiVocabMiner-V2-Preview-DELETE-ME" with its cards.
- The V2 note type is intentionally retained for normal setup use.
""".strip()
    )


if __name__ == "__main__":
    main()

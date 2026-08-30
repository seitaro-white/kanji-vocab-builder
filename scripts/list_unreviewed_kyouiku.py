"""Print Kyōiku kanji whose Anki cards have never been reviewed."""

import sys

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.jouyou_data import BY_GRADE


def main() -> int:
    """Query AnkiConnect and print the unreviewed Kyōiku kanji."""
    kyouiku = "".join(BY_GRADE[grade] for grade in range(1, 7))
    deck_name = connect.get_config().kanji_deck.name

    try:
        card_ids = connect.send_request("findCards", query=f'deck:"{deck_name}"')
        cards = connect.send_request("cardsInfo", cards=card_ids) if card_ids else []
    except Exception as error:
        print(error, file=sys.stderr)
        return 1

    reviewed = {
        card["fields"]["Kanji"]["value"]
        for card in cards
        if card.get("reps", 0) > 0 and "Kanji" in card.get("fields", {})
    }
    unreviewed = [kanji for kanji in kyouiku if kanji not in reviewed]

    print(f"Reviewed Kyōiku: {len(set(kyouiku) & reviewed)}/{len(kyouiku)}")
    print(f"Not reviewed: {len(unreviewed)}")
    print(" ".join(unreviewed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

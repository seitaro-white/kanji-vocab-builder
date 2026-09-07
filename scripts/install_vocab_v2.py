"""One-off installer for adding the V2 note type to an existing Anki deck."""

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.config import VOCAB_DECK_NAME, VOCAB_NOTE_TYPE_V2
from kanji_vocab_miner.setup import create_note_type_v2, update_note_type_v2


def install_vocab_v2() -> str:
    """Create or update V2 after verifying the existing vocabulary deck."""
    connect.send_request("version")

    deck_names = connect.send_request("deckNames")
    if VOCAB_DECK_NAME not in deck_names:
        raise RuntimeError(
            f"Existing vocabulary deck '{VOCAB_DECK_NAME}' was not found."
        )

    model_names = connect.send_request("modelNames")
    if VOCAB_NOTE_TYPE_V2 in model_names:
        update_note_type_v2()
        return f"Updated note type '{VOCAB_NOTE_TYPE_V2}'."

    create_note_type_v2()
    return f"Created note type '{VOCAB_NOTE_TYPE_V2}'."


def main() -> None:
    """Run the installer and print its bounded result."""
    try:
        result = install_vocab_v2()
    except Exception as error:
        raise SystemExit(f"V2 installation failed: {error}") from error

    print(result)
    print(f"Existing deck left unchanged: {VOCAB_DECK_NAME}")
    print("Next: uv run python scripts/preview_vocab_v2.py")


if __name__ == "__main__":
    main()

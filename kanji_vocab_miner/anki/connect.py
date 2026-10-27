"""AnkiConnect transport, collection access and supported legacy add helpers."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

import requests
from tqdm import tqdm

from kanji_vocab_miner.anki.note_types import (
    FIELDS,
    VOCAB_DECK_NAME,
    VOCAB_NOTE_TYPE,
    VOCAB_TAG,
)
from kanji_vocab_miner.anki.schemas import KanjiCard
from kanji_vocab_miner.config import get_config
from kanji_vocab_miner.jisho import JishoWord, fetch_jisho_word_furigana
from kanji_vocab_miner.review_status import KanjiReviewStatus
from kanji_vocab_miner.utils import is_kanji


def get_anki_url() -> str:
    """Get the AnkiConnect URL from configuration."""
    return get_config().ankiconnect.url


# Low Level
def send_request(action: str, **params: Any) -> Any:
    """Send an AnkiConnect version-6 request using raw wire parameters.

    Args:
        action: AnkiConnect action name, such as ``findNotes`` or ``addNote``.
        **params: Action-specific JSON-compatible parameters.

    Returns:
        The action's raw result, or None when result is absent or null. Callers
        at the Anki boundary interpret or validate action-specific responses.

    Raises:
        Exception: AnkiConnect reports an action error, or the HTTP request
            fails. Connection errors include guidance for starting Anki.
    """
    payload = {"action": action, "version": 6, "params": params}

    try:
        response = requests.post(get_anki_url(), json=payload)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            raise Exception(f"AnkiConnect error: {data['error']}")

        return data.get("result")
    except requests.RequestException as e:
        raise Exception(
            f"Failed to connect to Anki: {str(e)}. Make sure Anki is running with AnkiConnect installed."
        )


def update_note(card_id: int | None, fields: dict[str, str]) -> Any:
    """Send a partial field update for an existing note.

    Args:
        card_id: Historical parameter name for a note ID, not a card ID.
            Missing IDs are passed through to AnkiConnect without validation.
        fields: Exact Anki field names mapped to replacement content.
            Fields not present in this mapping remain unchanged.

    Returns:
        The raw updateNote result, normally None on success.

    Raises:
        Exception: AnkiConnect rejects the update or cannot be reached.
    """
    return send_request("updateNote", note={"id": card_id, "fields": fields})


def _get_card_info(card_id: int) -> Dict[str, Any]:
    """Read exactly one raw cardsInfo record.

    Args:
        card_id: Card ID to look up, not the owning note's ID.

    Returns:
        The sole card response, ready for model-specific validation.

    Raises:
        Exception: AnkiConnect fails, or returns zero or multiple cards.
    """

    response: list = send_request("cardsInfo", cards=[card_id])
    if len(response) > 1:
        raise Exception(f"Multiple cards returned for ID {card_id}!")
    if len(response) == 0:
        raise Exception(f"Card not found for ID {card_id}!")

    return response[0]


def get_kanji_card_info(card_id: int) -> KanjiCard:
    """Read and validate one card from the supported kanji note type.

    Args:
        card_id: Card ID to look up, not the owning note's ID.

    Returns:
        A KanjiCard with typed note fields and separate card and note IDs.

    Raises:
        Exception: AnkiConnect fails or does not return exactly one card.
        pydantic.ValidationError: The response does not match KanjiCard.
    """

    card_info = _get_card_info(card_id)
    return KanjiCard(**card_info)


# High Level
def get_current_card() -> Optional[KanjiCard]:
    """Read the reviewer's current card as a supported kanji card.

    Returns:
        The validated card, or None if guiCurrentCard supplies no card ID.

    Raises:
        Exception: AnkiConnect fails or the referenced card cannot be read.
        pydantic.ValidationError: The current card is not a supported kanji card.
    """

    result = send_request("guiCurrentCard")
    if result is None or "cardId" not in result:
        return None

    # Validate the note fields using the supported kanji-card schema.
    card_info = get_kanji_card_info(result["cardId"])
    if not card_info:
        return None

    return card_info


def extract_kanji_from_cards(cards: List[Dict[str, Any]]) -> List[str]:
    """Extract leading kanji from front-like fields in raw card records.

    Args:
        cards: AnkiConnect card records. The first field whose name contains
            ``front`` case-insensitively is used for each card.

    Returns:
        Leading kanji in input order, retaining duplicates. Missing, blank or
        non-kanji-leading front fields contribute no character. This legacy
        front-field reader is separate from the configured Kanji inventory.
    """
    kanji_list = []

    for card in cards:
        fields = card.get("fields", {})
        # Assuming the front field contains the kanji
        front_field = next((f for f in fields.keys() if "front" in f.lower()), None)

        if front_field and fields[front_field].get("value"):
            kanji = fields[front_field]["value"]
            # Only take the first character if it's a kanji
            if kanji and len(kanji) > 0 and is_kanji(kanji[0]):
                kanji_list.append(kanji[0])

    return kanji_list


def find_kanji_card_ids(kanji: str) -> List[int]:
    """Find all matching cards, including duplicates, in the kanji deck.

    Args:
        kanji: Kanji field value to place in the exact existing search query.

    Returns:
        Matching card IDs in AnkiConnect order, or an empty list if none match.

    Raises:
        Exception: Configuration or the AnkiConnect search cannot be loaded.
    """
    kanji_deck = get_config().kanji_deck.name
    query = f'deck:"{kanji_deck}" "Kanji:{kanji}"'
    return send_request("findCards", query=query) or []


def find_kanji_card_id(kanji: str) -> Optional[int]:
    """Find one matching kanji card using the best-effort CLI contract.

    Args:
        kanji: Kanji field value to search for in the configured kanji deck.

    Returns:
        The first matching card ID, or None when absent or loading fails.
        Loading failures also print a warning for the interactive caller.
    """
    try:
        card_ids = find_kanji_card_ids(kanji)
        return card_ids[0] if card_ids else None
    except Exception as e:
        # Preserve the non-fatal behavior used by the interactive reposition command.
        print(f"Warning: Failed to find Kanji card for '{kanji}': {str(e)}")
        return None


def get_kanji_review_status(kanji: str) -> KanjiReviewStatus:
    """Determine review status from every matching kanji card.

    Args:
        kanji: Kanji field value to search for in the configured kanji deck.

    Returns:
        NOT_IN_DECK when absent, REVIEWED when any matching card has reps > 0,
        or NOT_REVIEWED otherwise. Unlike the knowledge inventory, this check
        does not count a flagged new card as reviewed solely because of its flag.

    Raises:
        Exception: AnkiConnect cannot search or read the matching cards.
            Failures propagate rather than masquerading as an absent kanji.
    """
    card_ids = find_kanji_card_ids(kanji)
    if not card_ids:
        return KanjiReviewStatus.NOT_IN_DECK

    cards_info = send_request("cardsInfo", cards=card_ids)
    if any((card.get("reps") or 0) > 0 for card in cards_info):
        return KanjiReviewStatus.REVIEWED
    return KanjiReviewStatus.NOT_REVIEWED


def reposition_card_to_top(card_id: int) -> None:
    """Set a card's due value to zero using the existing queue workaround.

    Args:
        card_id: Card ID to reposition, not the owning note ID.

    Raises:
        Exception: The scheduling update fails; the error includes card_id.
    """
    try:
        # The 'due' field controls position (new cards) or day due (review cards).
        # Setting it to 0 puts it at the very front of the queue.
        send_request("setSpecificValueOfCard", card=card_id, keys=["due"], newValues=[0])
    except Exception as e:
        raise Exception(f"Failed to reposition card {card_id}: {str(e)}")


def prepare_note(word: JishoWord, reviewed_kanji: Set[str]) -> Dict[str, Any]:
    """Build a legacy note payload after fetching its target-word furigana.

    Args:
        word: Vocabulary entry with at least one English definition.
        reviewed_kanji: Kanji whose ruby readings should be hidden on the front.

    Returns:
        The eight-field legacy AnkiConnect note payload, including tags and
        duplicate options but excluding the destination deck name.

    Raises:
        Exception: Fetching or rendering the target-word furigana fails.
    """

    # Format the front with furigana HTML
    front = fetch_jisho_word_furigana(word.expression, reviewed_kanji)

    # Format the back with first definition
    back = word.definitions[0]

    # Create note using configured constants
    return {
        "modelName": VOCAB_NOTE_TYPE,
        "fields": {
            FIELDS["front"]: front,
            FIELDS["back"]: back,
            FIELDS["expression"]: word.expression,
            FIELDS["kana_reading"]: word.kana,
            FIELDS["grammar"]: word.parts_of_speech[0] if word.parts_of_speech else "",
            FIELDS["definition"]: word.definitions[0],
            FIELDS["additional_definitions"]: "\n".join(word.definitions[1:]),
            FIELDS["jlpt"]: f"JLPT N{word.jlpt}" if word.jlpt else "",
        },
        "tags": [VOCAB_TAG],
        "options": {"allowDuplicate": False},
    }


def add_vocab_note_to_deck(
    selected_words: List[JishoWord],
    deckname: Optional[str] = None,
    reviewed_kanji: Optional[Set[str]] = None,
) -> None:
    """Add legacy vocabulary notes independently, reporting a printed summary.

    Preparation and write failures are isolated per word. Duplicate notes are
    counted and skipped; other failures print their expression and error. This
    compatibility workflow does not perform the current V3 commit orchestration.

    Args:
        selected_words: Vocabulary entries in add order. An empty list performs
            no work and prints no summary.
        deckname: Destination deck, or None to use the vocabulary deck constant.
        reviewed_kanji: Kanji whose ruby readings should be hidden. None means
            empty knowledge; this helper does not load a kanji inventory.
    """
    if not selected_words:
        return

    deck = deckname if deckname is not None else VOCAB_DECK_NAME
    kanji_set = reviewed_kanji if reviewed_kanji is not None else set()

    added_count = 0
    duplicates_count = 0

    for word in tqdm(selected_words, desc="Adding notes", unit="note"):
        try:
            note = prepare_note(word, kanji_set) | {"deckName": deck}
        except Exception as e:
            print(f"Error preparing note for {word.expression}: {str(e)}")
            continue

        try:
            send_request("addNote", note=note)
            added_count += 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                duplicates_count += 1
            else:
                print(f"Error adding note for {word.expression}: {str(e)}")

    if duplicates_count > 0 and added_count > 0:
        print(f"Added {added_count} notes. Skipped {duplicates_count} duplicate notes.")
    elif duplicates_count > 0:
        print(f"No notes added. Skipped {duplicates_count} duplicate notes.")
    elif added_count > 0:
        print(f"Added {added_count} notes.")
    else:
        print("No notes were added.")


def _load_kanji_values(query: str) -> set[str]:
    """Read stored Kanji field values without normalizing collection content.

    Args:
        query: Complete AnkiConnect card search query.

    Returns:
        Distinct Kanji field values. Missing Kanji fields are skipped, while
        other malformed records remain errors for the calling policy to handle.
    """
    card_ids = send_request("findCards", query=query)
    if not card_ids:
        return set()
    cards = send_request("cardsInfo", cards=card_ids)
    return {
        card["fields"]["Kanji"]["value"]
        for card in cards
        if "fields" in card and "Kanji" in card["fields"]
    }


def get_reviewed_kanji(*, should_raise: bool = False) -> Set[str]:
    """Load the kanji knowledge inventory from the configured deck.

    Non-new cards and flag:1 cards qualify, including explicitly flagged new
    cards. Stored Kanji values are neither trimmed nor split into characters.

    Args:
        should_raise: Propagate loading errors for strict consumers such as the
            reader. Otherwise print a warning and return an empty set on error.

    Returns:
        Distinct qualifying Kanji field values; empty when there are no matches
        or a best-effort load fails.

    Raises:
        Exception: Loading or record interpretation fails and should_raise is
            True. The original exception is preserved.
    """
    try:
        kanji_deck = get_config().kanji_deck.name
        # The knowledge inventory also includes explicitly flagged new cards.
        return _load_kanji_values(f'deck:"{kanji_deck}" (-is:new OR flag:1)')
    except Exception as e:
        if should_raise:
            raise
        # Preserve best-effort behavior for existing CLI/card-rendering callers.
        print(f"Warning: Failed to get reviewed Kanji: {str(e)}")
        return set()


def get_all_kanji() -> Set[str]:
    """Load the deck's kanji inventory independently of review state.

    Returns:
        Distinct, unnormalized Kanji field values from every card in the deck.
        Loading failures print a warning and return an empty set. This inventory
        is the denominator for kanji coverage, not a measure of knowledge.
    """
    try:
        kanji_deck = get_config().kanji_deck.name
        return _load_kanji_values(f'deck:"{kanji_deck}"')
    except Exception as e:
        print(f"Warning: Failed to get all Kanji: {str(e)}")
        return set()


def count_vocab_notes_added_since(start_date: date) -> int:
    """Count distinct vocabulary notes created on or after ``start_date``.

    Anki note IDs encode their creation time in Unix milliseconds. Comparing
    their local creation date keeps the counter aligned with the date in the
    manual progress file and counts notes regardless of review state.

    Args:
        start_date: Inclusive creation-date boundary in the local time zone.

    Returns:
        The number of distinct vocabulary note IDs meeting the date boundary,
        regardless of card count, model version or review state.

    Raises:
        Exception: AnkiConnect cannot read the note inventory.
    """
    note_ids = send_request("findNotes", query=f'deck:"{VOCAB_DECK_NAME}"')
    return sum(
        datetime.fromtimestamp(int(note_id) / 1000).date() >= start_date
        for note_id in set(note_ids or [])
    )


def get_vocab_expressions() -> Set[str]:
    """Read unique vocabulary identities across legacy, V2 and V3 notes.

    Notes without a usable Expression field are ignored, allowing vocabulary
    notes to coexist with unrelated or malformed historical deck content.

    Returns:
        The deduplicated, trimmed, nonblank Expression values in the vocabulary
        deck, across legacy, V2, V3 and other notes with compatible fields.

    Raises:
        Exception: Inventory loading or record interpretation fails. This
            strict path never substitutes empty knowledge for a loading error.
    """
    note_ids = send_request("findNotes", query=f'deck:"{VOCAB_DECK_NAME}"') or []
    if not note_ids:
        return set()

    notes = send_request("notesInfo", notes=note_ids) or []
    return {
        expression
        for note in notes
        if (
            expression := note.get("fields", {})
            .get("Expression", {})
            .get("value", "")
            .strip()
        )
    }


def get_reviewed_vocab() -> List[str]:
    """Load all vocabulary identities using the best-effort legacy contract.

    Returns:
        Sorted, unique expressions regardless of review state. Despite the
        historical name, no reviewed-card filter is applied. Failures print a
        warning and return an empty list.
    """
    try:
        return sorted(get_vocab_expressions())
    except Exception as error:
        print(f"Warning: Failed to get reviewed Vocab: {str(error)}")
        return []

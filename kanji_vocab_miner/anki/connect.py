import requests
import json
from typing import List, Dict, Set, Any, Optional, Tuple
import re

# Update import to avoid circular dependency
from kanji_vocab_miner.utils import is_kanji
from kanji_vocab_miner.anki.schemas import KanjiCard
from kanji_vocab_miner.jisho import JishoWord, fetch_jisho_word_furigana
from kanji_vocab_miner.config import (
    load_config,
    VOCAB_DECK_NAME,
    VOCAB_NOTE_TYPE,
    VOCAB_TAG,
    FIELDS,
)

from tqdm import tqdm

# Lazy-loaded configuration
_config = None


def get_config():
    """Get or load the application configuration."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_anki_url() -> str:
    """Get the AnkiConnect URL from configuration."""
    return get_config().ankiconnect.url


# Low Level
def send_request(action: str, **params) -> Any:
    """
    Send a request to AnkiConnect API.

    Args:
        action: The action to perform
        **params: Additional parameters for the action

    Returns:
        The result from the API response

    Raises:
        Exception: If the response contains an error or connection fails
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


def update_note(card_id: int, fields: dict) -> None:
    """
    Edit a note in Anki.

    Args:
        card_id: The ID of the card to edit (notes and cards share same ID thankfully)
        fields: List of field names to edit
        new_values: List of new values for the fields
    """

    response = send_request("updateNote", note={"id": card_id, "fields": fields})
    return response


def _get_card_info(card_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific card.

    Args:
        card_id: The ID of the card

    Returns:
        Dictionary with card information or None if the card couldn't be found
    """

    response: list = send_request("cardsInfo", cards=[card_id])
    if len(response) > 1:
        raise Exception(f"Multiple cards returned for ID {card_id}!")
    if len(response) == 0:
        raise Exception(f"Card not found for ID {card_id}!")

    return response[0]


def get_kanji_card_info(card_id: int) -> KanjiCard:
    """
    Get detailed information about a specific card.

    Args:
        card_id: The ID of the card

    Returns:
        Dictionary with card information or None if the card couldn't be found
    """

    card_info = _get_card_info(card_id)
    return KanjiCard(**card_info)


# High Level
def get_current_card() -> Optional[Dict[str, Any]]:
    """
    Get information about the current card being reviewed.

    Returns:
        Dictionary with card information or None if no card is being reviewed
    """

    result = send_request("guiCurrentCard")
    if result is None or "cardId" not in result:
        return None

    # Get card info to extract the front field (Kanji)
    card_info = get_kanji_card_info(result["cardId"])
    if not card_info:
        return None

    return card_info


def extract_kanji_from_cards(cards: List[Dict[str, Any]]) -> List[str]:
    """
    Extract kanji characters from a list of cards.

    Args:
        cards: List of card information dictionaries

    Returns:
        List of kanji characters
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


def find_kanji_card_id(kanji: str) -> Optional[int]:
    """
    Find the card ID for a given Kanji in the configured kanji deck.

    Args:
        kanji: The Kanji character to search for.

    Returns:
        The card ID if found, otherwise None.
    """
    try:
        # Search for cards in the specific deck with the Kanji in the "Kanji" field
        kanji_deck = get_config().kanji_deck.name
        query = f'deck:"{kanji_deck}" "Kanji:{kanji}"'
        card_ids = send_request("findCards", query=query)

        if not card_ids:
            return None

        # If multiple cards are found (e.g., duplicates), just take the first one.
        return card_ids[0]

    except Exception as e:
        # If there's any error, just return None rather than breaking the app flow
        print(f"Warning: Failed to find Kanji card for '{kanji}': {str(e)}")
        return None


def reposition_card_to_top(card_id: int) -> None:
    """
    Reposition an Anki card to the top of its review queue (odue = 0).

    Args:
        card_id: The ID of the card to reposition.
    """
    try:
        # The 'odue' field controls the position in the queue for new/review cards.
        # Setting it to 0 puts it at the very front.
        send_request("setSpecificValueOfCard", card=card_id, keys=["odue"], newValues=[0])
    except Exception as e:
        raise Exception(f"Failed to reposition card {card_id}: {str(e)}")


def prepare_note(word: JishoWord) -> Dict[str, Any]:
    """Create an Anki note from a word dictionary"""

    # Format the front with furigana
    front = fetch_jisho_word_furigana(word.expression)

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
    selected_words: List[JishoWord], deckname: str = None
) -> None:
    """
    Add selected words to the vocabulary Anki deck.
    Handles duplicate notes by skipping them and continuing with others.

    Args:
        selected_words: List of word dictionaries containing word, reading, and definitions

    Returns:
        None
    """
    if not selected_words:
        return

    # Use VOCAB_DECK_NAME if deckname not specified
    deck = deckname if deckname is not None else VOCAB_DECK_NAME

    def add_non_duplicate_notes(notes: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Add non-duplicate notes to Anki

        Returns:
            Tuple of (added_count, duplicates_count)
        """
        # Check which notes can be added
        can_add_result = send_request("canAddNotesWithErrorDetail", notes=notes)

        # Filter out notes that would cause duplicate errors
        notes_to_add = [
            note for i, note in enumerate(notes) if can_add_result[i]["canAdd"]
        ]

        # Calculate counts
        duplicates_count = len(notes) - len(notes_to_add)

        # If no non-duplicate notes to add, return early
        if not notes_to_add:
            return 0, duplicates_count

        # Add only the non-duplicate notes
        send_request("addNotes", notes=notes_to_add)

        # Return counts
        return len(notes_to_add), duplicates_count

    # Prepare all notes
    prepared_notes = []
    for word in tqdm(selected_words, desc="Preparing notes", unit="note"):
        try:
            prepared_note = prepare_note(word) | {"deckName": deck}
            prepared_notes.append(prepared_note)
        except Exception as e:
            print(f"Error preparing note for {word.expression}: {str(e)}")
            continue

    # Add non-duplicate notes
    added_count, duplicates_count = add_non_duplicate_notes(prepared_notes)

    # Print summary
    if duplicates_count > 0 and added_count > 0:
        print(f"Added {added_count} notes. Skipped {duplicates_count} duplicate notes.")
    elif duplicates_count > 0:
        print(f"No notes added. Skipped {duplicates_count} duplicate notes.")
    elif added_count > 0:
        print(f"Added {added_count} notes.")
    else:
        print("No notes were added.")


def get_reviewed_kanji() -> Set[str]:
    """
    Get the set of Kanji that have been reviewed in the configured kanji deck.

    Returns:
        A set of reviewed Kanji characters

    Raises:
        Exception: If the operation fails
    """
    reviewed_kanji = set()

    try:
        # Get card IDs of reviewed cards in the Kanji deck
        # TODO: Remove the flag bit from this later as this is really just for me!
        kanji_deck = get_config().kanji_deck.name
        card_ids = send_request(
            "findCards", query=f'deck:"{kanji_deck}" (-is:new OR flag:1)'
        )

        if not card_ids:
            return reviewed_kanji

        # Get card info for each card
        cards_info = send_request("cardsInfo", cards=card_ids)

        # Extract Kanji from the Kanji field of each card (updated from Front to Kanji)
        for card in cards_info:
            if "fields" in card and "Kanji" in card["fields"]:
                kanji = card["fields"]["Kanji"]["value"]
                reviewed_kanji.add(kanji)

        return reviewed_kanji
    except Exception as e:
        # If there's any error, just return an empty set rather than breaking the app flow
        print(f"Warning: Failed to get reviewed Kanji: {str(e)}")
        return set()


def get_reviewed_vocab() -> List[str]:
    """
    Get a list of reviewed words from the vocabulary deck.
    Extracts the main word from the 'Front' field, typically from <ruby> tags.

    Returns:
        A list of reviewed words (main text from ruby tags or plain text).
    """
    reviewed_vocab: List[str] = []
    try:
        # Find card IDs of reviewed cards in the vocabulary deck
        # Reviewed cards are those that are not new.
        card_ids = send_request("findCards", query=f"deck:{VOCAB_DECK_NAME}")

        # Get card info for each card
        cards_info = send_request("cardsInfo", cards=card_ids)

        reviewed_vocab = [
            i["fields"]["Expression"]["value"]
            for i in cards_info
            if "Expression" in i["fields"] and
            # Added this in to deal with my mess of old cards that don't match the current format!
            i["fields"]["Expression"]["value"].strip() != ""
        ]

        return reviewed_vocab
    except Exception as e:
        # If there's any error, print a warning and return an empty list
        # This behavior is consistent with get_reviewed_kanji
        print(f"Warning: Failed to get reviewed Vocab: {str(e)}")
        return []

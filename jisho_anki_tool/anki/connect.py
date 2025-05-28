import requests
import json
from typing import List, Dict, Set, Any, Optional, Tuple
import re

# Update import to avoid circular dependency
from jisho_anki_tool.utils import format_furigana
from jisho_anki_tool.anki.schemas import KanjiCard
from jisho_anki_tool.jisho import JishoWord, fetch_jisho_word_furigana

from tqdm import tqdm

# Base URL for AnkiConnect
ANKI_CONNECT_URL = "http://localhost:8765"


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
        response = requests.post(ANKI_CONNECT_URL, json=payload)
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


def is_kanji(char: str) -> bool:
    """
    Check if a character is a Kanji.

    Args:
        char: The character to check

    Returns:
        True if the character is a Kanji, False otherwise
    """
    # Unicode ranges for Kanji: CJK Unified Ideographs (4E00-9FFF)
    if len(char) != 1:
        return False

    code_point = ord(char)
    return 0x4E00 <= code_point <= 0x9FFF


def prepare_note(word: JishoWord) -> Dict[str, Any]:
    """Create an Anki note from a word dictionary"""

    # Format the front with furigana
    front = fetch_jisho_word_furigana(word.expression)

    # Format the back with first definition
    back = word.definitions[0]

    # Create note
    return {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": front,
            "Back": back,
            "Expression": word.expression,
            "Kana Reading": word.kana,
            "Grammar": word.parts_of_speech[0],
            "Definition": word.definitions[0],
            "Additional Definitions": "\n".join(word.definitions[1:]),
            "JLPT": f"JLPT N{word.jlpt}",
            },
        "tags": ["jisho-anki-tool v2"],
        "options": {"allowDuplicate": False},
    }


def add_vocab_note_to_deck(selected_words: List[JishoWord], deckname:str="VocabularyNew") -> None:
    """
    Add selected words to the 'VocabularyNew' Anki deck.
    Handles duplicate notes by skipping them and continuing with others.

    Args:
        selected_words: List of word dictionaries containing word, reading, and definitions

    Returns:
        None
    """
    if not selected_words:
        return



    def add_non_duplicate_notes(notes: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Add non-duplicate notes to Anki

        Returns:
            Tuple of (added_count, duplicates_count)
        """
        # Check which notes can be added
        can_add_result = send_request("canAddNotes", notes=notes)

        # Filter out notes that would cause duplicate errors
        notes_to_add = [note for i, note in enumerate(notes) if can_add_result[i]]

        # Calculate counts
        duplicates_count = len(notes) - len(notes_to_add)

        # If no non-duplicate notes to add, return early
        if not notes_to_add:
            return 0, duplicates_count

        # Add only the non-duplicate notes
        send_request("addNotes", notes=notes_to_add)

        # Return counts
        return len(notes_to_add), duplicates_count

    try:
        # Prepare all notes
        prepared_notes = [
            prepare_note(word)
            for word in tqdm(selected_words, desc="Preparing notes", unit="note")
        ]

        # Add non-duplicate notes
        added_count, duplicates_count = add_non_duplicate_notes(prepared_notes)

        # Print summary
        if duplicates_count > 0 and added_count > 0:
            print(
                f"Added {added_count} notes. Skipped {duplicates_count} duplicate notes."
            )
        elif duplicates_count > 0:
            print(f"No notes added. Skipped {duplicates_count} duplicate notes.")
        elif added_count > 0:
            print(f"Added {added_count} notes.")
        else:
            print("No notes were added.")

    except Exception as e:
        print("Something went wrong! Dumping words to console:")
        print([w.expression for w in selected_words].join("\n"))
        raise Exception(f"Failed to add words to Anki: {str(e)}")



def get_reviewed_kanji() -> Set[str]:
    """
    Get the set of Kanji that have been reviewed in the 'All in one Kanji' deck.

    Returns:
        A set of reviewed Kanji characters

    Raises:
        Exception: If the operation fails
    """
    reviewed_kanji = set()

    try:
        # Get card IDs of reviewed cards in the Kanji deck
        # TODO: Remove the flag bit from this later as this is really just for me!
        # TODO: Replace the deckname with a constant or config value
        card_ids = send_request(
            "findCards", query='deck:"All In One Kanji" (-is:new OR flag:1)'
        )

        if not card_ids:
            return reviewed_kanji

        # Get card info for each card
        cards_info = send_request("cardsInfo", cards=card_ids)

        # Extract Kanji from the Kanji field of each card (updated from Front to Kanji)
        for card in cards_info:
            if "fields" in card and "Kanji" in card["fields"]:
                kanji = card["fields"]["Kanji"]["value"]
                # Remove HTML and get clean Kanji character
                kanji = (
                    kanji.replace("<div>", "")
                    .replace("</div>", "")
                    .replace("<br>", "")
                    .strip()
                )
                if kanji and len(kanji) == 1:  # Ensure it's a single character
                    reviewed_kanji.add(kanji)

        return reviewed_kanji
    except Exception as e:
        # If there's any error, just return an empty set rather than breaking the app flow
        print(f"Warning: Failed to get reviewed Kanji: {str(e)}")
        return set()


def get_reviewed_vocab() -> List[str]:
    """
    Get a list of reviewed words from the 'VocabularyNew' deck.
    Extracts the main word from the 'Front' field, typically from <ruby> tags.

    Returns:
        A list of reviewed words (main text from ruby tags or plain text).
    """
    reviewed_vocab: List[str] = []
    try:
        # Find card IDs of reviewed cards in the 'VocabularyNew' deck
        # Reviewed cards are those that are not new.
        card_ids = send_request("findCards", query="deck:VocabularyNew")

        if not card_ids:
            return reviewed_vocab

        # Get card info for each card
        cards_info = send_request("cardsInfo", cards=card_ids)

        # Extract the word from the 'Front' field of each card
        for card in cards_info:
            if "fields" in card and "Front" in card["fields"]:
                front_html_raw = card["fields"]["Front"]["value"]

                # Clean common wrapper HTML tags that might be present in the field value
                # Similar to cleaning in get_reviewed_kanji
                front_html_cleaned = (
                    front_html_raw.replace("<div>", "")
                    .replace("</div>", "")
                    .replace("<br>", "")
                    .strip()
                )

                word = None
                # Try to extract the main word from a <ruby> tag, e.g., <ruby>WORD<rt>reading</rt></ruby>
                ruby_match = re.search(
                    r"<ruby>(.*?)<rt>.*?</rt></ruby>", front_html_cleaned
                )

                if ruby_match:
                    word = ruby_match.group(1).strip()
                elif not re.search(
                    r"<[^>]+>", front_html_cleaned
                ):  # Check if it's plain text after cleaning
                    # If no ruby tag and no other HTML, assume the cleaned string is the word
                    word = front_html_cleaned
                # else: The field might contain other HTML structures not handled here, or is empty after cleaning.

                if word:  # Ensure word is not an empty string
                    reviewed_vocab.append(word)

        return reviewed_vocab
    except Exception as e:
        # If there's any error, print a warning and return an empty list
        # This behavior is consistent with get_reviewed_kanji
        print(f"Warning: Failed to get reviewed Vocab: {str(e)}")
        return []

import requests
import json
from typing import List, Dict, Set, Any, Optional, Tuple

# Update import to avoid circular dependency
from jisho_anki_tool.utils import format_furigana

# Base URL for AnkiConnect
ANKI_CONNECT_URL = "http://localhost:8765"

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
    payload = {
        "action": action,
        "version": 6,
        "params": params
    }

    try:
        response = requests.post(ANKI_CONNECT_URL, json=payload)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            raise Exception(f"AnkiConnect error: {data['error']}")

        return data.get("result")
    except requests.RequestException as e:
        raise Exception(f"Failed to connect to Anki: {str(e)}. Make sure Anki is running with AnkiConnect installed.")

def get_current_card() -> str:
    """
    Get the current Kanji card from Anki.

    Returns:
        The Kanji from the Kanji field of the current card

    Raises:
        Exception: If no card is open or the response is invalid
    """
    try:
        result = send_request("guiCurrentCard")

        if not result:
            raise Exception("No card is currently displayed in Anki.")

        # Extract the Kanji from the Kanji field (updated from Front to Kanji)
        if "fields" in result and "Kanji" in result["fields"]:
            kanji = result["fields"]["Kanji"]["value"]

            # Remove any HTML tags if present
            # Using a simple approach - a more robust approach would use BeautifulSoup
            kanji = kanji.replace("<div>", "").replace("</div>", "").replace("<br>", "").strip()

            return kanji
        else:
            raise Exception("The current card doesn't have a 'Kanji' field.")
    except Exception as e:
        raise Exception(f"Failed to get current card: {str(e)}")

def add_words_to_deck(selected_words: List[Dict[str, Any]]) -> List[Optional[int]]:
    """
    Add selected words to the 'VocabularyNew' Anki deck.
    Handles duplicate notes by skipping them and continuing with others.

    Args:
        selected_words: List of word dictionaries containing word, reading, and definitions

    Returns:
        List of IDs of the created notes (None values for duplicates)

    Raises:
        Exception: If the operation fails for reasons other than duplicates
    """
    if not selected_words:
        return []

    def prepare_note(word: Dict[str, Any]) -> Dict[str, Any]:
        """Create an Anki note from a word dictionary"""
        # Format the front with furigana
        front = format_furigana(word.get("word", ""), word.get("reading", ""))

        # Format the back with top 3 definitions
        definitions = word.get("definitions", [])
        if len(definitions) > 3:
            definitions = definitions[:3]
        back = "<br>".join(definitions)

        # Add JLPT level if available
        if word.get("jlpt"):
            back += f"<br><br><i>JLPT Level: N{word['jlpt']}</i>"

        # Create note
        return {
            "deckName": "VocabularyNew",
            "modelName": "Basic",
            "fields": {
                "Front": front,
                "Back": back
            },
            "tags": ["jisho-anki-tool"],
            "options": {
                "allowDuplicate": False
            }
        }

    def add_non_duplicate_notes(notes: List[Dict[str, Any]]) -> Tuple[List[Optional[int]], int, int]:
        """
        Add non-duplicate notes to Anki and return results

        Returns:
            Tuple of (result_ids, added_count, duplicates_count)
        """
        # Check which notes can be added
        can_add_result = send_request("canAddNotes", notes=notes)

        # Filter out notes that would cause duplicate errors
        notes_to_add = [note for i, note in enumerate(notes) if can_add_result[i]]

        # If no non-duplicate notes to add, return early
        if not notes_to_add:
            return [], 0, len(notes)

        # Add only the non-duplicate notes
        added_note_ids = send_request("addNotes", notes=notes_to_add)

        # Create result list matching the original input order
        result_ids = []
        add_index = 0

        for can_add in can_add_result:
            if can_add:
                # This note was added, use the ID from added_note_ids
                result_ids.append(added_note_ids[add_index])
                add_index += 1
            else:
                # This note was a duplicate, use None
                result_ids.append(None)

        # Count duplicates and added notes
        duplicates_count = sum(1 for id in result_ids if id is None)
        added_count = len(result_ids) - duplicates_count

        return result_ids, added_count, duplicates_count

    try:
        # Prepare all notes
        notes = [prepare_note(word) for word in selected_words]

        # Add non-duplicate notes
        result_ids, added_count, duplicates_count = add_non_duplicate_notes(notes)

        # Print summary
        if duplicates_count > 0:
            print(f"Added {added_count} notes. Skipped {duplicates_count} duplicate notes.")
        elif added_count > 0:
            print(f"Added {added_count} notes.")
        else:
            print("No notes were added.")

        return result_ids

    except Exception as e:
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
        card_ids = send_request("findCards", query="deck:current (-is:new OR flag:1)")

        if not card_ids:
            return reviewed_kanji

        # Get card info for each card
        cards_info = send_request("cardsInfo", cards=card_ids)

        # Extract Kanji from the Kanji field of each card (updated from Front to Kanji)
        for card in cards_info:
            if "fields" in card and "Kanji" in card["fields"]:
                kanji = card["fields"]["Kanji"]["value"]
                # Remove HTML and get clean Kanji character
                kanji = kanji.replace("<div>", "").replace("</div>", "").replace("<br>", "").strip()
                if kanji and len(kanji) == 1:  # Ensure it's a single character
                    reviewed_kanji.add(kanji)

        return reviewed_kanji
    except Exception as e:
        # If there's any error, just return an empty set rather than breaking the app flow
        print(f"Warning: Failed to get reviewed Kanji: {str(e)}")
        return set()

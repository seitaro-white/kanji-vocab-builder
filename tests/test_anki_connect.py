import pytest
import requests

from jisho_anki_tool.anki import connect
from jisho_anki_tool.anki.schemas import KanjiCard

def test_ping_anki():
    """
    Test if Anki is running and AnkiConnect is available.

    This basic test ensures that we can connect to the AnkiConnect API.
    All other tests will fail if this one doesn't pass.
    """
    try:
        # Try to get the AnkiConnect API version
        payload = {
            "action": "version",
            "version": 6
        }
        response = requests.post("http://localhost:8765", json=payload)
        response.raise_for_status()

        # Check if we got a valid response
        result = response.json()
        assert "result" in result, "Invalid response from AnkiConnect"
        assert result["result"] >= 6, "AnkiConnect version is too old"

        print(f"Successfully connected to AnkiConnect (version {result['result']})")
    except (requests.RequestException, ConnectionError) as e:
        pytest.fail(f"Failed to connect to Anki: {str(e)}. Make sure Anki is running with AnkiConnect installed.")

def test_get_current_card():
    """
    Test getting the current card from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. A card to be currently open in Anki with a "Kanji" field

    Will fail if Anki isn't running or no card is displayed.
    """
    # Get the current card
    card = connect.get_current_card()

    # Assert we got something back
    assert card, "No card returned from get_current_card"

def test_get_current_kanji():
    """
    Test getting the current kanji from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. A card to be currently open in Anki with a "Kanji" field

    Will fail if Anki isn't running or no card is displayed.
    """
    # Get the current kanji
    kanjicard = connect.get_current_card()

    # Assert it's not empty
    kanjichar = kanjicard.fields.Kanji.value
    # Unicode ranges for Kanji: CJK Unified Ideographs (4E00-9FFF)
    assert 0x4E00 <= ord(kanjichar) <= 0x9FFF


def test_get_reviewed_kanji():
    """
    Test getting all reviewed kanji from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. At least one kanji card to have been reviewed in the deck 'All in one Kanji'

    Will fail if Anki isn't running.
    """
    # Get the reviewed kanji set
    kanji_set = connect.get_reviewed_kanji()

    # Check that we got back a set
    assert len(kanji_set) > 0, "No kanji returned from get_reviewed_kanji"

    # If we got any kanji, check that they look like kanji
    for k in kanji_set:
        assert len(k) == 1, f"Kanji '{k}' is not a single character"
        assert 0x4E00 <= ord(k) <= 0x9FFF, f"Character '{k}' is not a kanji"

    print(f"Successfully retrieved {len(kanji_set)} reviewed kanji")


def test_get_due_cards():
    """
    Test getting due cards from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed.
    2. The deck "All in one Kanji" to exist.
    3. Optionally, some new cards that are due in the "All in one Kanji" deck
       to fully test the card data retrieval.

    Will fail if Anki isn't running.
    The test will pass if no due cards are found, but will print a message.
    """

    # Get due cards from the default deck "All in one Kanji"
    due_cards = connect.get_due_cards()

    # Assert that the result is a list (it could be empty)
    assert isinstance(due_cards, list), "get_due_cards should return a list."

    if not due_cards:
        print("No due cards found. Test passes as the function executed correctly.")

    else:
        print(f"Successfully retrieved {len(due_cards)} due cards.")
        # If cards are returned, check the structure of the first card
        first_card = due_cards[0]
        assert isinstance(first_card, dict), "Each item in the due_cards list should be a dictionary."
        assert "cardId" in first_card, "Due card data should contain 'cardId'."
        assert "fields" in first_card, "Due card data should contain 'fields'."
        assert "deckName" in first_card, "Due card data should contain 'deckName'."
        # New cards typically have queue and type 0
        assert "queue" in first_card and first_card["queue"] == 0, "Due new card should have queue 0."
        assert "type" in first_card and first_card["type"] == 0, "Due new card should have type 0."

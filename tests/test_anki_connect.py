import pytest
import requests

from jisho_anki_tool import anki_connect

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
    kanji = anki_connect.get_current_card()

    # Assert we got something back
    assert kanji, "No kanji returned from get_current_card"

    # Assert it's not empty
    assert len(kanji) > 0, "Returned kanji is empty"

    print(f"Successfully retrieved current card: {kanji}")

def test_get_reviewed_kanji():
    """
    Test getting all reviewed kanji from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. At least one kanji card to have been reviewed in the deck 'All in one Kanji'

    Will fail if Anki isn't running.
    """
    # Get the reviewed kanji set
    kanji_set = anki_connect.get_reviewed_kanji()

    # Check that we got back a set
    assert len(kanji_set) > 0, "No kanji returned from get_reviewed_kanji"

    # If we got any kanji, check that they look like kanji
    for k in kanji_set:
        assert len(k) == 1, f"Kanji '{k}' is not a single character"
        assert 0x4E00 <= ord(k) <= 0x9FFF, f"Character '{k}' is not a kanji"

    print(f"Successfully retrieved {len(kanji_set)} reviewed kanji")

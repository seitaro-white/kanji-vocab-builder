import pytest
import requests

from jisho_anki_tool.anki import connect
from jisho_anki_tool.anki.schemas import KanjiCard
from jisho_anki_tool.jisho import JishoWord # Added import

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

def test_get_reviewed_vocab():
    """
    Test getting all reviewed vocabulary from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. At least one vocabulary card to have been reviewed in the deck 'VocabularyNew'

    Will fail if Anki isn't running or no vocab has been reviewed.
    """
    # Get the reviewed vocab list
    vocab_list = connect.get_reviewed_vocab()

    # Check that we got back a list and it's not empty
    assert isinstance(vocab_list, list), "get_reviewed_vocab should return a list"
    assert len(vocab_list) > 0, "No vocabulary returned from get_reviewed_vocab"

    # If we got any vocab, check that they are non-empty strings
    for word in vocab_list:
        assert isinstance(word, str), f"Vocabulary item '{word}' is not a string"
        assert len(word) > 0, "Encountered an empty string in reviewed vocabulary"

    print(f"Successfully retrieved {len(vocab_list)} reviewed vocabulary words")


def test_prepare_note():
    """
    Test the prepare_note function for creating Anki note data.
    This test relies on the live functionality of `fetch_jisho_word_furigana`
    called within `prepare_note`.
    """
    # 1. Test with a standard word
    sample_word_full = JishoWord(
        expression="日本語",
        kana="にほんご",
        jlpt=3,
        definitions=["Japanese language", "The spoken and written language of Japan."],
        parts_of_speech=["Noun", "Proper Noun"]
    )

    # Call prepare_note - this will internally call fetch_jisho_word_furigana
    prepared_note_full = connect.prepare_note(sample_word_full)

    # Define expected output, assuming fetch_jisho_word_furigana("日本語") -> "日[に]本[ほん]語[ご]"
    expected_note_full = {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": "日本語[にほんご]", # Hardcoded expected furigana
            "Back": "Japanese language",
            "Expression": "日本語",
            "Kana Reading": "にほんご",
            "Grammar": "Noun",
            "Primary Definition": "Japanese language",
            "Additional Definitions": "The spoken and written language of Japan.",
            "JLPT": "JLPT N3",
        },
        "tags": ["jisho-anki-tool v2"],
        "options": {"allowDuplicate": False},
    }
    assert prepared_note_full == expected_note_full

    # 2. Test with minimal definitions and parts_of_speech (single items)
    sample_word_minimal = JishoWord(
        expression="学ぶ",
        kana="まなぶ",
        jlpt=4,
        definitions=["to learn"],
        parts_of_speech=["Verb"]
    )
    prepared_note_minimal = connect.prepare_note(sample_word_minimal)

    # Define expected output, assuming fetch_jisho_word_furigana("学ぶ") -> "学[まな]ぶ "
    expected_note_minimal = {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": "学[まな]ぶ ", # Hardcoded expected furigana
            "Back": "to learn",
            "Expression": "学ぶ",
            "Kana Reading": "まなぶ",
            "Grammar": "Verb",
            "Primary Definition": "to learn",
            "Additional Definitions": "",  # Expect empty string if only one definition
            "JLPT": "JLPT N4",
        },
        "tags": ["jisho-anki-tool v2"],
        "options": {"allowDuplicate": False},
    }
    assert prepared_note_minimal == expected_note_minimal

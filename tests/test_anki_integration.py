"""Integration tests for Anki setup and deck/note type creation.

These tests require:
1. Anki to be running
2. AnkiConnect plugin installed
3. "All In One Kanji" deck imported (for kanji deck tests)

These are real integration tests that interact with Anki.
"""

import pytest
from jisho_anki_tool.anki import connect
from jisho_anki_tool.config import VOCAB_DECK_NAME, VOCAB_NOTE_TYPE, FIELDS


# Test deck/note type names (use unique names to avoid conflicts)
TEST_DECK_NAME = "JishoAnki-TestDeck-DELETE-ME"
TEST_NOTE_TYPE = "JishoAnki-TestNoteType-DELETE-ME"


@pytest.fixture(scope="module")
def anki_connection():
    """Verify AnkiConnect is available before running tests."""
    try:
        version = connect.send_request("version")
        assert version >= 6, "AnkiConnect version too old"
        yield version
    except Exception as e:
        pytest.skip(f"AnkiConnect not available: {e}")


@pytest.fixture
def cleanup_test_deck():
    """Clean up test deck after test runs."""
    yield
    # Cleanup: Delete test deck if it exists
    try:
        connect.send_request("deleteDecks", decks=[TEST_DECK_NAME], cardsToo=True)
    except Exception:
        pass  # Deck might not exist, that's okay


# TODO: Remove this if it doesn't do anything I guess
@pytest.fixture
def cleanup_test_note_type():
    """Clean up test note type after test runs."""
    yield
    # Note: AnkiConnect doesn't have a deleteModel action, so we can't clean up
    # User will need to manually delete test note types from Anki
    # This is acceptable for integration tests


def test_ankiconnect_connectivity(anki_connection):
    """Test that we can connect to AnkiConnect."""
    assert anki_connection >= 6


def test_create_deck(anki_connection, cleanup_test_deck):
    """Test creating a new deck via AnkiConnect."""
    # Create deck
    result = connect.send_request("createDeck", deck=TEST_DECK_NAME)
    assert result is not None, "Failed to create deck"

    # Verify deck exists
    deck_names = connect.send_request("deckNames")
    assert TEST_DECK_NAME in deck_names, f"Deck {TEST_DECK_NAME} not found in deck list"


def test_create_deck_idempotent(anki_connection, cleanup_test_deck):
    """Test that creating a deck twice doesn't fail (idempotent operation)."""
    # Create deck first time
    connect.send_request("createDeck", deck=TEST_DECK_NAME)

    # Create deck second time - should not raise error
    try:
        result = connect.send_request("createDeck", deck=TEST_DECK_NAME)
        # AnkiConnect returns the deck ID even if it already exists
        assert result is not None
    except Exception as e:
        pytest.fail(f"Creating existing deck should be idempotent, but raised: {e}")


def test_create_note_type(anki_connection, cleanup_test_note_type):
    """Test creating a new note type via AnkiConnect."""
    # Define note type structure matching our vocab note type
    model_config = {
        "modelName": TEST_NOTE_TYPE,
        "inOrderFields": list(FIELDS.values()),
        "css": ".card { font-family: arial; font-size: 20px; text-align: center; }",
        "cardTemplates": [
            {
                "Name": "Card 1",
                "Front": "{{Front}}",
                "Back": "{{FrontSide}}<hr id=answer>{{Back}}",
            }
        ],
    }

    # Create note type
    result = connect.send_request("createModel", **model_config)
    assert result is not None, "Failed to create note type"

    # Verify note type exists
    model_names = connect.send_request("modelNames")
    assert TEST_NOTE_TYPE in model_names, f"Note type {TEST_NOTE_TYPE} not found"


def test_query_kanji_deck(anki_connection):
    """Test that we can query the 'All In One Kanji' deck."""
    try:
        # Try to find cards in the kanji deck
        card_ids = connect.send_request("findCards", query='deck:"All In One Kanji"')
        assert isinstance(card_ids, list), "Should return a list of card IDs"

        # We expect at least some cards in the deck
        if len(card_ids) == 0:
            pytest.skip("'All In One Kanji' deck appears empty - import the deck to run this test")

        print(f"Found {len(card_ids)} cards in 'All In One Kanji' deck")

    except Exception as e:
        if "deck was not found" in str(e).lower():
            pytest.skip("'All In One Kanji' deck not found - import it to run this test")
        raise


def test_add_note_to_deck(anki_connection, cleanup_test_deck):
    """Test adding a note to a deck."""
    # Create test deck first
    connect.send_request("createDeck", deck=TEST_DECK_NAME)

    # Use a basic note type that should exist (Basic)
    note = {
        "deckName": TEST_DECK_NAME,
        "modelName": "Basic",
        "fields": {"Front": "Test Front", "Back": "Test Back"},
        "tags": ["test"],
    }

    # Add note
    try:
        note_id = connect.send_request("addNote", note=note)
        assert note_id is not None, "Failed to add note"
        assert isinstance(note_id, int), "Note ID should be an integer"
        print(f"Successfully added note with ID: {note_id}")

    except Exception as e:
        if "model was not found" in str(e).lower():
            pytest.skip("'Basic' note type not found in Anki")
        raise


def test_prevent_deck_overwrite(anki_connection, cleanup_test_deck):
    """Test that we don't lose data when 'creating' an existing deck."""
    # Create deck and add a note
    connect.send_request("createDeck", deck=TEST_DECK_NAME)

    note = {
        "deckName": TEST_DECK_NAME,
        "modelName": "Basic",
        "fields": {"Front": "Important Data", "Back": "Do Not Lose"},
        "tags": ["important"],
    }

    try:
        note_id = connect.send_request("addNote", note=note)

        # Now "create" the deck again
        connect.send_request("createDeck", deck=TEST_DECK_NAME)

        # Verify the note still exists
        card_ids = connect.send_request("findCards", query=f'deck:"{TEST_DECK_NAME}"')
        assert len(card_ids) > 0, "Note was lost after 'recreating' deck"

        print(f"✓ Deck preserved with {len(card_ids)} card(s) after createDeck call")

    except Exception as e:
        if "model was not found" in str(e).lower():
            pytest.skip("'Basic' note type not found in Anki")
        raise


def test_vocab_deck_and_note_type_constants():
    """Test that our vocab deck constants are defined."""
    # These constants are used by the setup command
    assert VOCAB_DECK_NAME == "JishoAnki-Vocabulary"
    assert VOCAB_NOTE_TYPE == "JishoAnki-Vocab"
    assert len(FIELDS) == 8

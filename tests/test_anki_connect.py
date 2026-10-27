from collections.abc import Callable
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.anki.note_types import VOCAB_DECK_NAME
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.review_status import KanjiReviewStatus


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


def test_transport_preserves_action_payload_and_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.json.return_value = {"result": [123], "error": None}
    post = Mock(return_value=response)
    monkeypatch.setattr(connect, "get_anki_url", lambda: "http://anki.invalid:8765")
    monkeypatch.setattr(requests, "post", post)

    assert connect.send_request("findCards", query='deck:"Kanji"') == [123]
    post.assert_called_once_with(
        "http://anki.invalid:8765",
        json={"action": "findCards", "version": 6, "params": {"query": 'deck:"Kanji"'}},
    )
    response.raise_for_status.assert_called_once_with()


@pytest.mark.parametrize("data, expected", [({}, None), ({"result": None}, None)])
def test_transport_allows_missing_or_null_result(
    monkeypatch: pytest.MonkeyPatch, data: dict[str, None], expected: None
) -> None:
    response = Mock()
    response.json.return_value = data
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    assert connect.send_request("version") is expected


def test_transport_propagates_anki_error(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.json.return_value = {"result": None, "error": "invalid action"}
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    with pytest.raises(Exception, match="AnkiConnect error: invalid action"):
        connect.send_request("invalid")


def test_transport_wraps_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("HTTP 500")
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    with pytest.raises(Exception, match="Failed to connect to Anki: HTTP 500"):
        connect.send_request("version")
    response.json.assert_not_called()


def test_update_note_passes_note_id_and_returns_anki_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock(return_value="updated")
    monkeypatch.setattr(connect, "send_request", send)
    assert connect.update_note(card_id=101, fields={"Front": "学"}) == "updated"
    send.assert_called_once_with(
        "updateNote", note={"id": 101, "fields": {"Front": "学"}}
    )


@pytest.mark.parametrize("response", [[], [{}, {}]])
def test_card_read_rejects_missing_or_ambiguous_ids(
    monkeypatch: pytest.MonkeyPatch, response: list[dict[str, object]]
) -> None:
    send = Mock(return_value=response)
    monkeypatch.setattr(connect, "send_request", send)
    with pytest.raises(Exception, match="ID 77"):
        connect.get_kanji_card_info(77)
    send.assert_called_once_with("cardsInfo", cards=[77])


@pytest.mark.parametrize("response", [None, {}, {"other": 1}])
def test_current_card_returns_none_without_card_id(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, int] | None
) -> None:
    send = Mock(return_value=response)
    monkeypatch.setattr(connect, "send_request", send)
    assert connect.get_current_card() is None
    send.assert_called_once_with("guiCurrentCard")


def test_reposition_preserves_card_action_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock()
    monkeypatch.setattr(connect, "send_request", send)
    connect.reposition_card_to_top(77)
    send.assert_called_once_with(
        "setSpecificValueOfCard", card=77, keys=["due"], newValues=[0]
    )
    send.side_effect = RuntimeError("unavailable")
    with pytest.raises(Exception, match="Failed to reposition card 77: unavailable"):
        connect.reposition_card_to_top(77)


def test_reviewed_kanji_keeps_flag_rule_and_field_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        connect, "get_config",
        lambda: SimpleNamespace(kanji_deck=SimpleNamespace(name="Kanji Deck")),
    )
    send = Mock(side_effect=[
        [1, 2, 3, 4],
        [
            {"fields": {"Kanji": {"value": "学"}}},
            {"fields": {"Kanji": {"value": "学"}}},
            {"fields": {"Front": {"value": "校"}}},
            {"fields": {"Kanji": {"value": " 学校 "}}},
        ],
    ])
    monkeypatch.setattr(connect, "send_request", send)
    assert connect.get_reviewed_kanji() == {"学", " 学校 "}
    assert send.call_args_list[0].kwargs == {
        "query": 'deck:"Kanji Deck" (-is:new OR flag:1)'
    }
    assert send.call_args_list[1].kwargs == {"cards": [1, 2, 3, 4]}


@pytest.mark.parametrize("loader", [connect.get_all_kanji, connect.get_reviewed_kanji])
def test_kanji_inventory_failures_remain_best_effort(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    loader: Callable[[], set[str]],
) -> None:
    monkeypatch.setattr(
        connect, "send_request", Mock(side_effect=RuntimeError("offline"))
    )
    assert loader() == set()
    assert "offline" in capsys.readouterr().out


def test_vocab_inventory_is_strict_but_legacy_wrapper_is_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        connect, "send_request", Mock(side_effect=RuntimeError("offline"))
    )
    with pytest.raises(RuntimeError, match="offline"):
        connect.get_vocab_expressions()
    assert connect.get_reviewed_vocab() == []


def test_reviewed_vocab_wrapper_returns_all_expressions_sorted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: {"猫", "学校", "犬"})
    assert connect.get_reviewed_vocab() == ["学校", "犬", "猫"]


def test_empty_inventories_skip_info_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    send = Mock(return_value=None)
    monkeypatch.setattr(connect, "send_request", send)
    assert connect.get_reviewed_kanji(should_raise=True) == set()
    assert connect.get_all_kanji() == set()
    assert connect.get_vocab_expressions() == set()
    assert [call.args[0] for call in send.call_args_list] == [
        "findCards", "findCards", "findNotes"
    ]


def test_strict_reviewed_inventory_propagates_malformed_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock(side_effect=[
        [1, 2],
        [{"fields": {"Kanji": {"value": "学"}}}, {"fields": {"Kanji": {}}}],
    ])
    monkeypatch.setattr(connect, "send_request", send)
    with pytest.raises(KeyError, match="value"):
        connect.get_reviewed_kanji(should_raise=True)


def test_legacy_add_keeps_skipping_preparation_duplicates_and_write_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    words = [
        JishoWord(expression=expression, kana="かな", jlpt=0, definitions=["meaning"])
        for expression in ("失敗", "重複", "中断", "成功")
    ]
    prepare = Mock(side_effect=[
        ValueError("bad reading"),
        {"fields": {"Expression": "重複"}},
        {"fields": {"Expression": "中断"}},
        {"fields": {"Expression": "成功"}},
    ])
    send = Mock(side_effect=[RuntimeError("duplicate"), RuntimeError("offline"), 123])
    monkeypatch.setattr(connect, "prepare_note", prepare)
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "tqdm", lambda values, **kwargs: values)

    assert connect.add_vocab_note_to_deck(words, "Custom Deck", {"学"}) is None
    assert all(call.args[1] == {"学"} for call in prepare.call_args_list)
    expressions = [
        call.kwargs["note"]["fields"]["Expression"] for call in send.call_args_list
    ]
    assert expressions == ["重複", "中断", "成功"]
    assert all(
        call.kwargs["note"]["deckName"] == "Custom Deck"
        for call in send.call_args_list
    )
    assert capsys.readouterr().out.splitlines() == [
        "Error preparing note for 失敗: bad reading",
        "Error adding note for 中断: offline",
        "Added 1 notes. Skipped 1 duplicate notes.",
    ]


def test_get_all_kanji_ignores_review_state(monkeypatch):
    """get_all_kanji returns every kanji in the deck, regardless of review state."""
    def fake_send(action, **params):
        if action == "findCards":
            # Must NOT filter by review state — we want the whole deck.
            assert "is:new" not in params["query"]
            return [1, 2, 3]
        if action == "cardsInfo":
            return [
                {"fields": {"Kanji": {"value": "学"}}},
                {"fields": {"Kanji": {"value": "校"}}},
                {"fields": {"Kanji": {"value": "学"}}},  # duplicate collapses in a set
            ]
        raise AssertionError(f"unexpected action {action}")

    monkeypatch.setattr(connect, "send_request", fake_send)
    assert connect.get_all_kanji() == {"学", "校"}


def test_get_kanji_review_status_uses_all_duplicate_cards(monkeypatch):
    """Any duplicate with at least one review makes the kanji reviewed."""
    monkeypatch.setattr(
        connect,
        "get_config",
        lambda: SimpleNamespace(kanji_deck=SimpleNamespace(name="Kanji Deck")),
    )

    def fake_send(action, **params):
        if action == "findCards":
            assert params["query"] == 'deck:"Kanji Deck" "Kanji:学"'
            return [10, 20]
        if action == "cardsInfo":
            assert params["cards"] == [10, 20]
            return [{"reps": 0}, {"reps": 3}]
        raise AssertionError(f"unexpected action {action}")

    monkeypatch.setattr(connect, "send_request", fake_send)

    assert connect.get_kanji_review_status("学") == KanjiReviewStatus.REVIEWED


def test_get_kanji_review_status_distinguishes_new_and_missing(monkeypatch):
    monkeypatch.setattr(
        connect,
        "get_config",
        lambda: SimpleNamespace(kanji_deck=SimpleNamespace(name="Kanji Deck")),
    )
    responses = iter([[10], [{"reps": 0}], []])
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: next(responses))

    assert connect.get_kanji_review_status("新") == KanjiReviewStatus.NOT_REVIEWED
    assert connect.get_kanji_review_status("無") == KanjiReviewStatus.NOT_IN_DECK


def test_count_vocab_notes_added_since_uses_note_creation_dates(monkeypatch):
    def note_id(year, month, day):
        return int(datetime(year, month, day, 12).timestamp() * 1000)

    old_note = note_id(2026, 9, 2)
    first_tracked_note = note_id(2026, 9, 3)
    later_note = note_id(2026, 9, 4)
    def fake_send(action, **params):
        assert action == "findNotes"
        assert params["query"] == f'deck:"{VOCAB_DECK_NAME}"'
        return [old_note, first_tracked_note, later_note, later_note]

    monkeypatch.setattr(connect, "send_request", fake_send)

    assert connect.count_vocab_notes_added_since(date(2026, 9, 3)) == 2


@pytest.fixture
def kanji_card_with_restore():
    """
    Yields (card_id, original_due) for a known kanji card and restores its
    due value after the test, so Anki's queue order is not permanently changed.
    """
    card_id = connect.find_kanji_card_id("使")
    assert card_id is not None, "Could not find kanji card for 使 — is the deck loaded?"
    info = connect.send_request("cardsInfo", cards=[card_id])
    original_due = info[0]["due"]
    yield card_id, original_due
    connect.send_request("setSpecificValueOfCard", card=card_id, keys=["due"], newValues=[original_due])


@pytest.mark.integration
def test_reposition_card_to_top(kanji_card_with_restore):
    """Test that reposition_card_to_top moves a card to due=0 in its queue."""
    card_id, original_due = kanji_card_with_restore
    connect.reposition_card_to_top(card_id)
    info = connect.send_request("cardsInfo", cards=[card_id])
    assert info[0]["due"] == 0


@pytest.mark.integration
def test_find_kanji_card_id_returns_none_for_unknown():
    """Test that find_kanji_card_id returns None for a character not in the deck."""
    result = connect.find_kanji_card_id("X")
    assert result is None


def test_get_vocab_expressions_reads_unique_note_fields(monkeypatch) -> None:
    """Duplicate detection reads Expression once per note across model types."""
    calls = []

    def fake_send(action, **params):
        calls.append((action, params))
        if action == "findNotes":
            return [10, 20, 30, 40, 50, 60]
        assert action == "notesInfo"
        return [
            {
                "modelName": "MyJapaneseVocabulary",
                "fields": {"Expression": {"value": "学校"}},
            },
            {
                "modelName": "MyJapaneseVocabularyV2",
                "fields": {"Expression": {"value": " 猫 "}},
            },
            {
                "modelName": "MyJapaneseVocabularyV3",
                "fields": {"Expression": {"value": "犬"}},
            },
            {"fields": {"Expression": {"value": "学校"}}},
            {"fields": {"Front": {"value": "legacy malformed"}}},
            {"fields": {"Expression": {"value": "  "}}},
        ]

    monkeypatch.setattr(connect, "send_request", fake_send)

    assert connect.get_vocab_expressions() == {"学校", "猫", "犬"}
    assert calls == [
        ("findNotes", {"query": 'deck:"KanjiVocabMiner-Vocabulary"'}),
        ("notesInfo", {"notes": [10, 20, 30, 40, 50, 60]}),
    ]


def test_prepare_legacy_note_keeps_primary_and_additional_definitions(monkeypatch):
    """Legacy serialization retains all definitions without live Jisho access."""
    monkeypatch.setattr(
        connect, "fetch_jisho_word_furigana",
        lambda expression, reviewed: "<ruby>日本語<rt>にほんご</rt></ruby>",
    )
    sample_word_full = JishoWord(
        expression="日本語",
        kana="にほんご",
        jlpt=3,
        definitions=["Japanese language", "The spoken and written language of Japan."],
        parts_of_speech=["Noun", "Proper Noun"]
    )

    prepared_note_full = connect.prepare_note(sample_word_full, set())

    expected_note_full = {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": "<ruby>日本語<rt>にほんご</rt></ruby>",
            "Back": "Japanese language",
            "Expression": "日本語",
            "Kana Reading": "にほんご",
            "Grammar": "Noun",
            "Definition": "Japanese language",
            "Additional Definitions": "The spoken and written language of Japan.",
            "JLPT": "JLPT N3",
        },
        "tags": ["kanji-vocab-miner"],
        "options": {"allowDuplicate": False},
    }
    assert prepared_note_full == expected_note_full


def test_prepare_legacy_note_leaves_additional_definitions_empty_for_one_sense(
    monkeypatch,
):
    monkeypatch.setattr(
        connect, "fetch_jisho_word_furigana",
        lambda expression, reviewed: "<ruby>学<rt>まな</rt></ruby>ぶ",
    )
    sample_word_minimal = JishoWord(
        expression="学ぶ",
        kana="まなぶ",
        jlpt=4,
        definitions=["to learn"],
        parts_of_speech=["Verb"]
    )
    prepared_note_minimal = connect.prepare_note(sample_word_minimal, set())

    expected_note_minimal = {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": "<ruby>学<rt>まな</rt></ruby>ぶ",
            "Back": "to learn",
            "Expression": "学ぶ",
            "Kana Reading": "まなぶ",
            "Grammar": "Verb",
            "Definition": "to learn",
            "Additional Definitions": "",  # Expect empty string if only one definition
            "JLPT": "JLPT N4",
        },
        "tags": ["kanji-vocab-miner"],
        "options": {"allowDuplicate": False},
    }
    assert prepared_note_minimal == expected_note_minimal

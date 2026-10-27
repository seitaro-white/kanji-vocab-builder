"""Stored-furigana maintenance uses note-level access without live Anki."""

from unittest.mock import Mock

import pytest

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.anki.furigana_sync import (
    FuriganaChange,
    _update_stored_furigana,
    sync_vocab_furigana,
)


@pytest.mark.parametrize(
    "stored, reviewed, expected_html, has_changes",
    [
        ("かな", set(), "かな", False),
        (
            "学[がく]び 方[かた]",
            {"学"},
            (
                '<ruby>学<rt class="known">がく</rt></ruby>び'
                '<ruby>方<rt>かた</rt></ruby>'
            ),
            True,
        ),
        (
            '<ruby>学<rt class="known">がく</rt></ruby>',
            set(),
            "<ruby>学<rt>がく</rt></ruby>",
            True,
        ),
    ],
)
def test_stored_furigana_returns_named_change(
    stored: str, reviewed: set[str], expected_html: str, has_changes: bool
) -> None:
    change = _update_stored_furigana(stored, reviewed)

    assert change == FuriganaChange(html=expected_html, has_changes=has_changes)
    assert change.html == expected_html
    assert change.has_changes is has_changes


def test_sync_updates_front_and_cue_once_per_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock(side_effect=[
        [10],
        [{
            "noteId": 10,
            "fields": {
                "Front": {"value": "<ruby>学校<rt>がっこう</rt></ruby>"},
                "JapaneseCue": {"value": "<ruby>教育<rt>きょういく</rt></ruby>"},
                "JapaneseDefinition": {"value": "教育を行う所。"},
            },
        }],
        None,
    ])
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: {"学", "校", "教", "育"})

    assert sync_vocab_furigana() == 1
    assert send.call_args.kwargs == {
        "note": {
            "id": 10,
            "fields": {
                "Front": '<ruby>学校<rt class="known">がっこう</rt></ruby>',
                "JapaneseCue": '<ruby>教育<rt class="known">きょういく</rt></ruby>',
            },
        }
    }
    assert [call.args[0] for call in send.call_args_list] == [
        "findNotes", "notesInfo", "updateNote"
    ]


def test_sync_migrates_compatible_models_by_note_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock(side_effect=[
        [10, 20, 30, 40],
        [
            {
                "noteId": 10, "cardId": 999, "modelName": "MyJapaneseVocabulary",
                "fields": {"Front": {"value": "学[がく]ぶ"}},
            },
            {
                "note": 20, "modelName": "MyJapaneseVocabularyV2",
                "fields": {"JapaneseCue": {
                    "value": '<ruby>学<rt class="known">がく</rt></ruby>'
                }},
            },
            {
                "noteId": 30, "modelName": "MyJapaneseVocabularyV3",
                "fields": {
                    "Front": {"value": "犬[いぬ]"},
                    "JapaneseDefinition": {"value": "犬[いぬ]"},
                    "Example": {"value": "犬[いぬ]"},
                },
            },
            {"noteId": 40, "fields": {"Front": {"value": "かな"}}},
        ],
        None, None,
    ])
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: {"学"})

    assert sync_vocab_furigana() == 2
    assert send.call_args_list[0].kwargs == {
        "query": 'deck:"KanjiVocabMiner-Vocabulary"'
    }
    assert send.call_args_list[1].kwargs == {"notes": [10, 20, 30, 40]}
    assert [call.kwargs["note"] for call in send.call_args_list[2:]] == [
        {"id": 10, "fields": {"Front": '<ruby>学<rt class="known">がく</rt></ruby>ぶ'}},
        {"id": 30, "fields": {"Front": "<ruby>犬<rt>いぬ</rt></ruby>"}},
    ]


def test_sync_continues_after_note_write_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    send = Mock(side_effect=[
        [10, 20],
        [
            {"noteId": note_id, "fields": {"Front": {"value": "学[がく]"}}}
            for note_id in [10, 20]
        ],
        RuntimeError("write failed"), None,
    ])
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    assert sync_vocab_furigana() == 1
    assert "Failed to update note 10: write failed" in capsys.readouterr().out
    assert send.call_args_list[-1].kwargs["note"]["id"] == 20


@pytest.mark.parametrize(
    "responses",
    [[RuntimeError("offline")], [[10], RuntimeError("offline")], [[]]],
)
def test_sync_returns_zero_for_empty_or_unavailable_inventory(
    monkeypatch: pytest.MonkeyPatch, responses: list[object]
) -> None:
    send = Mock(side_effect=responses)
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    assert sync_vocab_furigana() == 0
    assert all(call.args[0] != "updateNote" for call in send.call_args_list)


@pytest.mark.parametrize(
    "note, error_type",
    [
        ({"noteId": 10, "fields": None}, AttributeError),
        ({"noteId": 10, "fields": {"Front": None}}, AttributeError),
        ({"noteId": 10, "fields": {"Front": {"value": 123}}}, TypeError),
    ],
)
def test_sync_preserves_malformed_note_failures(
    monkeypatch: pytest.MonkeyPatch,
    note: dict[str, object],
    error_type: type[Exception],
) -> None:
    send = Mock(side_effect=[[10], [note]])
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())

    with pytest.raises(error_type):
        sync_vocab_furigana()

    assert [call.args[0] for call in send.call_args_list] == ["findNotes", "notesInfo"]


def test_sync_keeps_missing_note_id_for_existing_write_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock(side_effect=[[10], [{"fields": {"Front": {"value": "学[がく]"}}}], None])
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())

    assert sync_vocab_furigana() == 1
    assert send.call_args.kwargs == {
        "note": {"id": None, "fields": {"Front": "<ruby>学<rt>がく</rt></ruby>"}}
    }


def test_sync_with_empty_reviewed_set_unhides_stored_ruby(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = Mock(side_effect=[
        [10],
        [{"noteId": 10, "fields": {"Front": {
            "value": '<ruby>学<rt class="known">がく</rt></ruby>'
        }}}],
        None,
    ])
    monkeypatch.setattr(connect, "send_request", send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    assert sync_vocab_furigana() == 1
    assert send.call_args.kwargs["note"] == {
        "id": 10, "fields": {"Front": "<ruby>学<rt>がく</rt></ruby>"}
    }

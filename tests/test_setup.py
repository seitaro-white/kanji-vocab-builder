"""Tests for isolated Anki vocabulary model setup."""

from unittest.mock import patch

import pytest

from kanji_vocab_miner.config import VOCAB_NOTE_TYPE_V2, VOCAB_V2_FIELDS
from kanji_vocab_miner.setup import (
    create_note_type_v2,
    run_setup,
    update_note_type_v2,
)
from scripts.install_vocab_v2 import install_vocab_v2


def test_create_note_type_v2_uses_exact_field_order() -> None:
    """The V2 model is created with the stable thirteen-field schema."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v2()

    _, kwargs = send_request.call_args
    assert kwargs["modelName"] == VOCAB_NOTE_TYPE_V2
    assert kwargs["inOrderFields"] == list(VOCAB_V2_FIELDS.values())


def test_v2_recognition_template_matches_legacy_card_one_behavior() -> None:
    """Recognition retains the established Japanese-to-English card."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v2()

    recognition = send_request.call_args.kwargs["cardTemplates"][0]
    assert recognition == {
        "Name": "Recognition",
        "Front": '<div class="japanese">{{Front}}</div>',
        "Back": (
            '<div class="show-all-furigana">{{FrontSide}}</div>\n\n'
            "<hr id=answer>\n\n{{Back}}"
        ),
    }


def test_v2_recall_front_is_fully_conditional() -> None:
    """A blank Recall field prevents Anki from generating the recall card."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v2()

    recall = send_request.call_args.kwargs["cardTemplates"][1]
    assert recall["Name"] == "Recall"
    assert recall["Front"].strip() == (
        '{{#Recall}}\n<div class="japanese-cue">{{JapaneseCue}}</div>\n'
        "{{/Recall}}"
    )


def test_v2_recall_answer_has_japanese_content_and_source_only() -> None:
    """Recall answers reveal Japanese target details without English definitions."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v2()

    answer = send_request.call_args.kwargs["cardTemplates"][1]["Back"]
    for field in (
        "{{JapaneseCue}}",
        "{{Front}}",
        "{{Kana Reading}}",
        "{{DefinitionSource}}",
        "{{DefinitionURL}}",
    ):
        assert field in answer
    assert "show-all-furigana" in answer
    assert "{{Back}}" not in answer
    assert "{{Definition}}" not in answer
    assert "{{Additional Definitions}}" not in answer


def test_v2_css_extends_furigana_styles_for_recall_content() -> None:
    """Only V2 receives styling for cue senses, readings, and provenance."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v2()

    css = send_request.call_args.kwargs["css"]
    assert "rt.known" in css
    assert ".show-all-furigana rt.known" in css
    assert ".japanese-cue" in css
    assert ".sense" in css
    assert ".definition-source" in css


def test_update_note_type_v2_validates_fields_then_updates_only_v2() -> None:
    """Existing V2 models are validated before template and CSS updates."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        send_request.side_effect = [list(VOCAB_V2_FIELDS.values()), None, None]
        update_note_type_v2()

    assert send_request.call_args_list[0].args == ("modelFieldNames",)
    assert send_request.call_args_list[0].kwargs == {"modelName": VOCAB_NOTE_TYPE_V2}
    for call in send_request.call_args_list[1:]:
        assert call.kwargs["model"]["name"] == VOCAB_NOTE_TYPE_V2


def test_update_note_type_v2_rejects_incompatible_schema() -> None:
    """Schema drift fails actionably before any model mutation request."""
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        send_request.return_value = ["Front", "Back"]

        with pytest.raises(ValueError, match="incompatible fields"):
            update_note_type_v2()

    send_request.assert_called_once_with(
        "modelFieldNames", modelName=VOCAB_NOTE_TYPE_V2
    )


def test_run_setup_creates_only_v2_model_on_a_fresh_install() -> None:
    """Fresh setup has no legacy-model compatibility branch."""
    responses = [6, 123, [], 456, ["All in One Kanji"]]
    with (
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
        patch("kanji_vocab_miner.setup.console.print"),
    ):
        send_request.side_effect = responses
        assert run_setup() is True

    model_mutations = [
        call
        for call in send_request.call_args_list
        if call.args[0] in {"createModel", "updateModelTemplates", "updateModelStyling"}
    ]
    assert len(model_mutations) == 1
    assert model_mutations[0].kwargs["modelName"] == VOCAB_NOTE_TYPE_V2


def test_one_off_installer_adds_v2_model_to_existing_vocab_deck() -> None:
    """The migration helper installs V2 without touching notes or legacy models."""
    with (
        patch("scripts.install_vocab_v2.connect.send_request") as send_request,
        patch("scripts.install_vocab_v2.create_note_type_v2") as create_v2,
    ):
        send_request.side_effect = [6, ["KanjiVocabMiner-Vocabulary"], []]
        install_vocab_v2()

    create_v2.assert_called_once_with()
    assert [call.args[0] for call in send_request.call_args_list] == [
        "version",
        "deckNames",
        "modelNames",
    ]


def test_run_setup_updates_existing_v2_model() -> None:
    """Setup validates and refreshes an installed V2 model."""
    responses = [
        6,
        123,
        [VOCAB_NOTE_TYPE_V2],
        list(VOCAB_V2_FIELDS.values()),
        None,
        None,
        ["All in One Kanji"],
    ]
    with (
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
        patch("kanji_vocab_miner.setup.console.print"),
    ):
        send_request.side_effect = responses
        assert run_setup() is True

    model_mutations = [
        call
        for call in send_request.call_args_list
        if call.args[0] in {"createModel", "updateModelTemplates", "updateModelStyling"}
    ]
    assert model_mutations
    assert all(
        call.kwargs.get("modelName") == VOCAB_NOTE_TYPE_V2
        or call.kwargs.get("model", {}).get("name") == VOCAB_NOTE_TYPE_V2
        for call in model_mutations
    )

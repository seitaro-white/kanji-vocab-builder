"""Tests for isolated Anki vocabulary model setup."""

import re
from unittest.mock import patch

import pytest

from kanji_vocab_miner.config import (
    AppConfig,
    VOCAB_NOTE_TYPE_V2,
    VOCAB_NOTE_TYPE_V3,
    VOCAB_V2_FIELDS,
    VOCAB_V3_FIELDS,
)
from kanji_vocab_miner.setup import (
    create_note_type_v2,
    create_note_type_v3,
    run_setup,
    update_note_type_v2,
    update_note_type_v3,
    validate_prerequisites,
)
from scripts.install_vocab_v2 import install_vocab_v2


@pytest.fixture
def setup_config(tmp_path):
    """Run real prompt provisioning inside the test's configuration directory."""
    config = AppConfig(llm={"prompt_path": tmp_path / "prompt.md"})
    with patch("kanji_vocab_miner.setup.load_config", return_value=config):
        yield config


def test_prerequisites_require_v3_but_not_older_models() -> None:
    """Production startup requires V3, independently of legacy and V2."""
    responses = [6, ["KanjiVocabMiner-Vocabulary", "All in One Kanji"], [VOCAB_NOTE_TYPE_V2]]
    with (
        patch("kanji_vocab_miner.setup.load_config", return_value=AppConfig()),
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
    ):
        send_request.side_effect = responses
        is_valid, errors = validate_prerequisites()

    assert is_valid is False
    assert any("MyJapaneseVocabularyV3" in error for error in errors)
    assert all("'MyJapaneseVocabularyV2'" not in error for error in errors)
    assert all("'MyJapaneseVocabulary'" not in error for error in errors)


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
    assert _css_declarations(css, "rt.known")["display"] == "none"
    assert (
        _css_declarations(css, ".show-all-furigana rt.known")["display"]
        == "ruby-text"
    )
    assert _css_declarations(css, ".japanese-cue")["font-size"] == "1.35em"
    assert _css_declarations(css, ".sense + .sense")["margin-top"] == "0.75em"
    assert _css_declarations(css, ".definition-source")["font-size"] == "0.65em"


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


def test_setup_installs_prompt_even_when_anki_is_unavailable(setup_config) -> None:
    with (
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
        patch("kanji_vocab_miner.setup.console.print"),
    ):
        send_request.side_effect = RuntimeError("Anki is unavailable")
        result = run_setup()

    assert result is False
    content = setup_config.llm.prompt_path.read_text(encoding="utf-8")
    assert "register, connotation" in content
    assert "Why these kanji" in content
    send_request.assert_called_once_with("version")


def test_run_setup_creates_only_v3_model_on_a_fresh_install(setup_config) -> None:
    """Fresh setup creates V3 without mutating older models."""
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
    assert model_mutations[0].kwargs["modelName"] == VOCAB_NOTE_TYPE_V3


def test_one_off_installer_adds_v2_model_to_existing_vocab_deck() -> None:
    """The migration helper installs V2 without touching notes or legacy models."""
    with patch("scripts.install_vocab_v2.connect.send_request") as send_request:
        send_request.side_effect = [6, ["KanjiVocabMiner-Vocabulary"], [], 123]
        result = install_vocab_v2()

    assert result == "Created note type 'MyJapaneseVocabularyV2'."
    assert [call.args[0] for call in send_request.call_args_list] == [
        "version", "deckNames", "modelNames", "createModel",
    ]
    assert send_request.call_args.kwargs["modelName"] == VOCAB_NOTE_TYPE_V2


def test_run_setup_updates_existing_v3_model(setup_config) -> None:
    """Setup validates and refreshes an installed V3 model only."""
    responses = [
        6,
        123,
        [VOCAB_NOTE_TYPE_V2, VOCAB_NOTE_TYPE_V3],
        list(VOCAB_V3_FIELDS.values()),
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
        call.kwargs.get("modelName") == VOCAB_NOTE_TYPE_V3
        or call.kwargs.get("model", {}).get("name") == VOCAB_NOTE_TYPE_V3
        for call in model_mutations
    )


def test_v3_recognition_enriches_answers_and_preserves_recall() -> None:
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v3()

    kwargs = send_request.call_args.kwargs
    assert kwargs["modelName"] == VOCAB_NOTE_TYPE_V3
    assert kwargs["inOrderFields"] == list(VOCAB_V3_FIELDS.values())
    recognition, recall = kwargs["cardTemplates"]
    assert recognition["Front"] == '<div class="japanese">{{Front}}</div>'
    back = recognition["Back"]
    assert back.index("{{Back}}") < back.index("Nuance") < back.index("Example") < back.index("Why these kanji")
    for field in ("Nuance", "Example", "KanjiExplanation"):
        assert "{{#" + field + "}}" in back
        assert "{{/" + field + "}}" in back
    assert recall == create_v2_templates()[1]
    target_style = _css_declarations(kwargs["css"], ".example-target")
    assert target_style["color"] == "red"
    assert target_style["font-weight"] == "bold"


def create_v2_templates() -> list[dict]:
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        create_note_type_v2()
    return send_request.call_args.kwargs["cardTemplates"]


def test_update_note_type_v3_validates_before_mutating_only_v3() -> None:
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        send_request.side_effect = [list(VOCAB_V3_FIELDS.values()), None, None]
        update_note_type_v3()

    assert send_request.call_args_list[0].kwargs == {"modelName": VOCAB_NOTE_TYPE_V3}
    assert all(call.kwargs["model"]["name"] == VOCAB_NOTE_TYPE_V3 for call in send_request.call_args_list[1:])


def test_update_note_type_v3_rejects_incompatible_schema_before_mutation() -> None:
    with patch("kanji_vocab_miner.setup.connect.send_request") as send_request:
        send_request.return_value = list(VOCAB_V2_FIELDS.values())
        with pytest.raises(ValueError, match="incompatible fields"):
            update_note_type_v3()
    send_request.assert_called_once_with("modelFieldNames", modelName=VOCAB_NOTE_TYPE_V3)


def _css_declarations(css: str, selector: str) -> dict[str, str]:
    rule = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert rule is not None, f"Missing CSS rule for {selector}"
    return {
        name.strip(): value.strip()
        for name, value in (
            declaration.split(":", 1)
            for declaration in rule.group(1).split(";")
            if declaration.strip()
        )
    }

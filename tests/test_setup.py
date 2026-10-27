"""Setup presentation and caller wiring, with reusable Anki operations mocked."""

from unittest.mock import patch

import pytest

from kanji_vocab_miner.anki.note_types import (
    VOCAB_NOTE_TYPE_V2,
    VOCAB_NOTE_TYPE_V3,
    VOCAB_V2_FIELDS,
    VOCAB_V3_FIELDS,
)
from kanji_vocab_miner.config import AppConfig
from kanji_vocab_miner.setup import run_setup, validate_prerequisites
from scripts.install_vocab_v2 import install_vocab_v2


@pytest.fixture
def setup_config(tmp_path):
    """Run real prompt provisioning inside the test's configuration directory."""
    config = AppConfig(llm={"prompt_path": tmp_path / "prompt.md"})
    with patch("kanji_vocab_miner.setup.load_config", return_value=config):
        yield config


def test_prerequisites_require_v3_but_not_older_models() -> None:
    """Production startup requires V3, independently of legacy and V2."""
    deck_names = ["KanjiVocabMiner-Vocabulary", "All in One Kanji"]
    with (
        patch("kanji_vocab_miner.setup.load_config", return_value=AppConfig()),
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
    ):
        send_request.side_effect = [6, deck_names, [VOCAB_NOTE_TYPE_V2], deck_names]
        is_valid, errors = validate_prerequisites()

    assert is_valid is False
    assert len(errors) == 1
    assert "MyJapaneseVocabularyV3" in errors[0]
    assert "'MyJapaneseVocabularyV2'" not in errors[0]
    assert "'MyJapaneseVocabulary'" not in errors[0]


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
    with (
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
        patch("kanji_vocab_miner.setup.console.print"),
    ):
        send_request.side_effect = [6, 123, [], 456, ["All in One Kanji"]]
        assert run_setup() is True

    model_mutations = [
        call for call in send_request.call_args_list
        if call.args[0] in {"createModel", "updateModelTemplates", "updateModelStyling"}
    ]
    assert len(model_mutations) == 1
    assert model_mutations[0].kwargs["modelName"] == VOCAB_NOTE_TYPE_V3


def test_run_setup_updates_existing_v3_model(setup_config) -> None:
    """Setup validates and refreshes an installed V3 model only."""
    with (
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
        patch("kanji_vocab_miner.setup.console.print"),
    ):
        send_request.side_effect = [
            6, 123, [VOCAB_NOTE_TYPE_V2, VOCAB_NOTE_TYPE_V3],
            list(VOCAB_V3_FIELDS.values()), None, None, ["All in One Kanji"],
        ]
        assert run_setup() is True

    model_mutations = [
        call for call in send_request.call_args_list
        if call.args[0] in {"createModel", "updateModelTemplates", "updateModelStyling"}
    ]
    assert [call.args[0] for call in model_mutations] == [
        "updateModelTemplates", "updateModelStyling"
    ]
    assert all(
        call.kwargs["model"]["name"] == VOCAB_NOTE_TYPE_V3
        for call in model_mutations
    )


def test_setup_refuses_to_refresh_incompatible_v3(setup_config) -> None:
    with (
        patch("kanji_vocab_miner.setup.connect.send_request") as send_request,
        patch("kanji_vocab_miner.setup.console.print"),
    ):
        send_request.side_effect = [6, 123, [VOCAB_NOTE_TYPE_V3], ["Front", "Back"]]
        assert run_setup() is False
    assert [call.args[0] for call in send_request.call_args_list] == [
        "version", "createDeck", "modelNames", "modelFieldNames"
    ]


def test_one_off_installer_adds_v2_model_to_existing_vocab_deck() -> None:
    """The migration helper installs V2 without touching notes or legacy models."""
    with patch("scripts.install_vocab_v2.connect.send_request") as send_request:
        send_request.side_effect = [6, ["KanjiVocabMiner-Vocabulary"], [], 123]
        assert install_vocab_v2() == "Created note type 'MyJapaneseVocabularyV2'."

    assert [call.args[0] for call in send_request.call_args_list] == [
        "version", "deckNames", "modelNames", "createModel"
    ]
    assert send_request.call_args.kwargs["modelName"] == VOCAB_NOTE_TYPE_V2


def test_one_off_installer_refreshes_only_existing_v2() -> None:
    with patch("scripts.install_vocab_v2.connect.send_request") as send_request:
        send_request.side_effect = [
            6, ["KanjiVocabMiner-Vocabulary"], [VOCAB_NOTE_TYPE_V2, VOCAB_NOTE_TYPE_V3],
            list(VOCAB_V2_FIELDS.values()), None, None,
        ]
        assert install_vocab_v2() == "Updated note type 'MyJapaneseVocabularyV2'."
    assert [call.args[0] for call in send_request.call_args_list] == [
        "version", "deckNames", "modelNames", "modelFieldNames",
        "updateModelTemplates", "updateModelStyling",
    ]
    assert all(
        call.kwargs["model"]["name"] == VOCAB_NOTE_TYPE_V2
        for call in send_request.call_args_list[-2:]
    )

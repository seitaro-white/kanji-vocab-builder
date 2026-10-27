"""Pure vocabulary schemas, templates and the stored-ruby CSS contract."""

import re
from dataclasses import FrozenInstanceError

import pytest

from kanji_vocab_miner.anki.note_types import (
    FIELDS,
    LEGACY_FIELDS,
    LEGACY_VOCAB_NOTE_TYPE,
    VOCAB_DECK_NAME,
    VOCAB_NOTE_TYPE,
    VOCAB_NOTE_TYPE_V2,
    VOCAB_NOTE_TYPE_V3,
    VOCAB_TAG,
    VOCAB_V2_FIELDS,
    VOCAB_V3_FIELDS,
    CardTemplate,
    NoteTypeDefinition,
    vocab_note_type_v2,
    vocab_note_type_v3,
)


def test_vocab_constants_defined() -> None:
    assert VOCAB_DECK_NAME == "KanjiVocabMiner-Vocabulary"
    assert VOCAB_NOTE_TYPE == "MyJapaneseVocabulary"
    assert VOCAB_TAG == "kanji-vocab-miner"
    assert len(FIELDS) == 8


def test_v2_fields_extend_legacy_fields_in_intended_order() -> None:
    assert LEGACY_VOCAB_NOTE_TYPE == "MyJapaneseVocabulary"
    assert VOCAB_NOTE_TYPE_V2 == "MyJapaneseVocabularyV2"
    assert LEGACY_FIELDS is FIELDS
    assert VOCAB_NOTE_TYPE == LEGACY_VOCAB_NOTE_TYPE
    assert list(VOCAB_V2_FIELDS.values()) == [
        "Front", "Back", "Expression", "Kana Reading", "Grammar", "Definition",
        "Additional Definitions", "JLPT", "JapaneseDefinition", "JapaneseCue",
        "Recall", "DefinitionSource", "DefinitionURL",
    ]
    definition = vocab_note_type_v2()
    assert definition.model_name == VOCAB_NOTE_TYPE_V2
    assert definition.field_names == tuple(VOCAB_V2_FIELDS.values())


def test_v3_fields_extend_v2_fields_in_exact_order() -> None:
    assert VOCAB_NOTE_TYPE_V3 == "MyJapaneseVocabularyV3"
    assert list(VOCAB_V3_FIELDS.values()) == list(VOCAB_V2_FIELDS.values()) + [
        "Nuance", "Example", "KanjiExplanation",
    ]
    definition = vocab_note_type_v3()
    assert definition.model_name == VOCAB_NOTE_TYPE_V3
    assert definition.field_names == tuple(VOCAB_V3_FIELDS.values())


@pytest.mark.parametrize("definition", [vocab_note_type_v2(), vocab_note_type_v3()])
def test_definitions_expose_immutable_named_concepts(
    definition: NoteTypeDefinition,
) -> None:
    assert isinstance(definition, NoteTypeDefinition)
    assert isinstance(definition.field_names, tuple)
    assert isinstance(definition.templates, tuple)
    assert all(isinstance(template, CardTemplate) for template in definition.templates)
    assert [template.name for template in definition.templates] == ["Recognition", "Recall"]
    # Dynamic writes test runtime protection without invalid typed assignments.
    with pytest.raises(FrozenInstanceError):
        setattr(definition, "model_name", "Different model")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(definition.templates[0], "front_template", "Changed template")  # noqa: B010


def test_v2_recognition_template_matches_legacy_card_one_behavior() -> None:
    assert vocab_note_type_v2().templates[0] == CardTemplate(
        name="Recognition",
        front_template='<div class="japanese">{{Front}}</div>',
        back_template=(
            '<div class="show-all-furigana">{{FrontSide}}</div>\n\n'
            "<hr id=answer>\n\n{{Back}}"
        ),
    )


def test_v2_recall_front_is_fully_conditional() -> None:
    recall = vocab_note_type_v2().templates[1]
    assert recall.name == "Recall"
    assert recall.front_template.strip() == (
        '{{#Recall}}\n<div class="japanese-cue">{{JapaneseCue}}</div>\n{{/Recall}}'
    )


def test_v2_recall_answer_has_japanese_content_and_source_only() -> None:
    answer = vocab_note_type_v2().templates[1].back_template
    for field in (
        "{{JapaneseCue}}", "{{Front}}", "{{Kana Reading}}",
        "{{DefinitionSource}}", "{{DefinitionURL}}",
    ):
        assert field in answer
    assert "show-all-furigana" in answer
    assert "{{Back}}" not in answer
    assert "{{Definition}}" not in answer
    assert "{{Additional Definitions}}" not in answer


def test_v2_css_extends_furigana_styles_for_recall_content() -> None:
    css = vocab_note_type_v2().css
    assert _css_declarations(css, "rt.known")["display"] == "none"
    assert (
        _css_declarations(css, ".show-all-furigana rt.known")["display"]
        == "ruby-text"
    )
    assert _css_declarations(css, ".japanese-cue")["font-size"] == "1.35em"
    assert _css_declarations(css, ".sense + .sense")["margin-top"] == "0.75em"
    assert _css_declarations(css, ".definition-source")["font-size"] == "0.65em"


def test_v3_recognition_enriches_answers_and_preserves_recall() -> None:
    definition = vocab_note_type_v3()
    recognition, recall = definition.templates
    assert recognition.front_template == '<div class="japanese">{{Front}}</div>'
    back = recognition.back_template
    positions = [
        back.index(label)
        for label in ("{{Back}}", "Nuance", "Example", "Why these kanji")
    ]
    assert positions == sorted(positions)
    for field in ("Nuance", "Example", "KanjiExplanation"):
        assert "{{#" + field + "}}" in back
        assert "{{/" + field + "}}" in back
    assert recall == vocab_note_type_v2().templates[1]
    assert _css_declarations(definition.css, "rt.known")["display"] == "none"
    assert (
        _css_declarations(definition.css, ".show-all-furigana rt.known")["display"]
        == "ruby-text"
    )
    target_style = _css_declarations(definition.css, ".example-target")
    assert target_style["color"] == "red"
    assert target_style["font-weight"] == "bold"


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

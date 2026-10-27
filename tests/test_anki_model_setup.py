"""Reusable model setup preserves exact Anki actions and safe refresh ordering."""

from collections.abc import Callable
from unittest.mock import call, patch

import pytest

from kanji_vocab_miner.anki.model_setup import (
    create_note_type_v2,
    create_note_type_v3,
    update_note_type_v2,
    update_note_type_v3,
)
from kanji_vocab_miner.anki.note_types import (
    NoteTypeDefinition,
    vocab_note_type_v2,
    vocab_note_type_v3,
)


@pytest.mark.parametrize(
    "create, definition",
    [
        (create_note_type_v2, vocab_note_type_v2()),
        (create_note_type_v3, vocab_note_type_v3()),
    ],
)
def test_create_serializes_named_definition_at_anki_boundary(
    create: Callable[[], None], definition: NoteTypeDefinition
) -> None:
    with patch("kanji_vocab_miner.anki.model_setup.connect.send_request") as send:
        create()
    send.assert_called_once_with(
        "createModel",
        modelName=definition.model_name,
        inOrderFields=list(definition.field_names),
        css=definition.css,
        cardTemplates=[
            {
                "Name": template.name,
                "Front": template.front_template,
                "Back": template.back_template,
            }
            for template in definition.templates
        ],
    )


@pytest.mark.parametrize(
    "definition, update",
    [
        (vocab_note_type_v2(), update_note_type_v2),
        (vocab_note_type_v3(), update_note_type_v3),
    ],
)
def test_refresh_validates_then_updates_only_templates_and_css(
    definition: NoteTypeDefinition, update: Callable[[], None]
) -> None:
    """Refresh matches creation without mutating fields, notes or older models."""
    with patch("kanji_vocab_miner.anki.model_setup.connect.send_request") as send:
        send.side_effect = [list(definition.field_names), None, None]
        update()

    assert send.call_args_list == [
        call("modelFieldNames", modelName=definition.model_name),
        call("updateModelTemplates", model={
            "name": definition.model_name,
            "templates": {
                template.name: {
                    "Front": template.front_template,
                    "Back": template.back_template,
                }
                for template in definition.templates
            },
        }),
        call(
            "updateModelStyling",
            model={"name": definition.model_name, "css": definition.css},
        ),
    ]


@pytest.mark.parametrize(
    "definition, update",
    [
        (vocab_note_type_v2(), update_note_type_v2),
        (vocab_note_type_v3(), update_note_type_v3),
    ],
)
@pytest.mark.parametrize("reordered", [False, True])
def test_refresh_rejects_incompatible_fields_before_mutation(
    definition: NoteTypeDefinition, update: Callable[[], None], reordered: bool
) -> None:
    fields = list(definition.field_names)
    actual_fields = list(reversed(fields)) if reordered else ["Front", "Back"]
    with patch("kanji_vocab_miner.anki.model_setup.connect.send_request") as send:
        send.return_value = actual_fields
        with pytest.raises(ValueError) as error:
            update()
    assert str(error.value) == (
        f"Note type '{definition.model_name}' has incompatible fields. "
        f"Expected {fields}, received {actual_fields}."
    )
    send.assert_called_once_with("modelFieldNames", modelName=definition.model_name)


@pytest.mark.parametrize("update", [update_note_type_v2, update_note_type_v3])
def test_refresh_propagates_field_read_failure_without_mutation(
    update: Callable[[], None],
) -> None:
    with patch("kanji_vocab_miner.anki.model_setup.connect.send_request") as send:
        send.side_effect = RuntimeError("offline")
        with pytest.raises(RuntimeError, match="offline"):
            update()
    assert send.call_count == 1

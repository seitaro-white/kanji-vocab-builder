"""Serialize note-type definitions for creation and safe Anki model refresh."""

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.anki.note_types import (
    NoteTypeDefinition,
    vocab_note_type_v2,
    vocab_note_type_v3,
)


def _validate_model_fields(definition: NoteTypeDefinition) -> None:
    """Require the installed model to match the definition's exact field order.

    Args:
        definition: Expected model identity and ordered field names.

    Raises:
        ValueError: The installed fields differ in names or order.
        Exception: AnkiConnect cannot read the installed model.
    """
    actual_fields = connect.send_request(
        "modelFieldNames", modelName=definition.model_name
    )
    expected_fields = list(definition.field_names)
    if actual_fields != expected_fields:
        raise ValueError(
            f"Note type '{definition.model_name}' has incompatible fields. "
            f"Expected {expected_fields}, received {actual_fields}."
        )


def _create_note_type(definition: NoteTypeDefinition) -> None:
    """Serialize a complete definition into one createModel request.

    Args:
        definition: Model schema, stylesheet and ordered card templates.
    """
    connect.send_request(
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


def _update_note_type(definition: NoteTypeDefinition) -> None:
    """Validate a definition before serializing template and styling updates.

    Args:
        definition: Existing model's expected schema and replacement format.
    """
    _validate_model_fields(definition)
    connect.send_request(
        "updateModelTemplates",
        model={
            "name": definition.model_name,
            "templates": {
                template.name: {
                    "Front": template.front_template,
                    "Back": template.back_template,
                }
                for template in definition.templates
            },
        },
    )
    connect.send_request(
        "updateModelStyling",
        model={"name": definition.model_name, "css": definition.css},
    )


def create_note_type_v2() -> None:
    """Create the isolated V2 vocabulary note type.

    Raises:
        Exception: AnkiConnect cannot create the model.
    """
    _create_note_type(vocab_note_type_v2())


def update_note_type_v2() -> None:
    """Refresh only V2 templates and CSS, preserving fields and existing notes.

    Raises:
        ValueError: The installed V2 model has incompatible field names or order.
        Exception: AnkiConnect cannot read or update the model.
    """
    _update_note_type(vocab_note_type_v2())


def create_note_type_v3() -> None:
    """Create the isolated V3 vocabulary note type.

    Raises:
        Exception: AnkiConnect cannot create the model.
    """
    _create_note_type(vocab_note_type_v3())


def update_note_type_v3() -> None:
    """Refresh only V3 templates and CSS, preserving fields and existing notes.

    Raises:
        ValueError: The installed V3 model has incompatible field names or order.
        Exception: AnkiConnect cannot read or update the model.
    """
    _update_note_type(vocab_note_type_v3())

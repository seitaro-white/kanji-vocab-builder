"""Anki record projection retains note identity and original stored HTML."""

from dataclasses import FrozenInstanceError

import pytest

from kanji_vocab_miner.anki.schemas import VocabNoteFurigana


def test_note_furigana_projects_only_supported_fields() -> None:
    note = VocabNoteFurigana.from_anki_note({
        "noteId": 10,
        "note": 20,
        "cardId": 999,
        "modelName": "Compatible custom model",
        "fields": {
            "Front": {"value": " 学[がく] "},
            "JapaneseCue": {"value": "<div>学ぶ。</div>"},
            "JapaneseDefinition": {"value": "Unmodified definition"},
        },
    })

    assert note == VocabNoteFurigana(
        note_id=10, front_html=" 学[がく] ", japanese_cue_html="<div>学ぶ。</div>"
    )
    # Exercise runtime protection without an invalid typed assignment.
    with pytest.raises(FrozenInstanceError):
        setattr(note, "note_id", 999)  # noqa: B010


@pytest.mark.parametrize("raw, note_id", [({}, None), ({"note": 20}, 20)])
def test_note_furigana_preserves_legacy_id_and_missing_field_defaults(
    raw: dict[str, int], note_id: int | None
) -> None:
    assert VocabNoteFurigana.from_anki_note(raw) == VocabNoteFurigana(
        note_id=note_id, front_html="", japanese_cue_html=""
    )

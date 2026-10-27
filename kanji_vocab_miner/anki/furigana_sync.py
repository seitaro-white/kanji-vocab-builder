"""Maintain stored vocabulary ruby across compatible legacy, V2 and V3 notes."""

import re
from dataclasses import dataclass

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.anki.note_types import VOCAB_DECK_NAME
from kanji_vocab_miner.anki.schemas import VocabNoteFurigana
from kanji_vocab_miner.furigana import update_furigana_visibility


@dataclass(frozen=True)
class FuriganaChange:
    """The result of updating one stored furigana fragment.

    Attributes:
        html: Content after any legacy migration and ruby-visibility update.
        has_changes: Whether this content needs writing back to the note.
            Legacy-notation migration always counts as a change.
    """

    html: str
    has_changes: bool


def _update_stored_furigana(
    stored_html: str, reviewed_kanji: set[str]
) -> FuriganaChange:
    """Migrate legacy notation and update review-dependent ruby visibility.

    Args:
        stored_html: Existing field content, either ruby HTML or legacy notation.
        reviewed_kanji: Kanji whose ruby readings should receive rt.known.

    Returns:
        Updated content and an explicit indication of whether it needs saving.
    """
    if re.search(r"[\u4e00-\u9fff]\[", stored_html):
        migrated = re.sub(
            r"([\u4e00-\u9fff])\[([^\]]+)\]",
            r"<ruby>\1<rt>\2</rt></ruby>",
            stored_html,
        )
        migrated = re.sub(r"([\u3040-\u309f]) ", r"\1", migrated)
        updated_html, _ = update_furigana_visibility(migrated, reviewed_kanji)
        return FuriganaChange(html=updated_html, has_changes=True)

    updated_html, has_changes = update_furigana_visibility(stored_html, reviewed_kanji)
    return FuriganaChange(html=updated_html, has_changes=has_changes)


def _changed_furigana_fields(
    note: VocabNoteFurigana, reviewed_kanji: set[str]
) -> dict[str, str]:
    """Build the changed-field mapping for one AnkiConnect note update.

    Args:
        note: Stored note content eligible for furigana maintenance.
        reviewed_kanji: Kanji whose ruby readings should be hidden.

    Returns:
        Wire field names mapped to changed content. Empty or unchanged fields
        are omitted; definitions and enrichment fields are never included.
    """
    updated_fields: dict[str, str] = {}
    for name, content in (
        ("Front", note.front_html),
        ("JapaneseCue", note.japanese_cue_html),
    ):
        if content:
            change = _update_stored_furigana(content, reviewed_kanji)
            if change.has_changes:
                updated_fields[name] = change.html
    return updated_fields


def sync_vocab_furigana() -> int:
    """Update review-dependent furigana once per compatible vocabulary note.

    Front and optional JapaneseCue changes share a single note-level write;
    definitions and enrichment fields are untouched. Reviewed-kanji loading
    remains best-effort: empty knowledge can reveal previously hidden ruby.
    Individual write failures warn and do not prevent later note updates.

    Returns:
        The number of notes successfully updated, or zero if loading the note
        inventory fails. Malformed stored content is not silently repaired.
    """
    reviewed_kanji = connect.get_reviewed_kanji()
    try:
        note_ids = connect.send_request(
            "findNotes", query=f'deck:"{VOCAB_DECK_NAME}"'
        ) or []
        raw_notes = connect.send_request("notesInfo", notes=note_ids) if note_ids else []
    except Exception:
        return 0

    updated_count = 0
    for raw_note in raw_notes:
        note = VocabNoteFurigana.from_anki_note(raw_note)
        updated_fields = _changed_furigana_fields(note, reviewed_kanji)
        if not updated_fields:
            continue

        try:
            connect.update_note(note.note_id, updated_fields)
            updated_count += 1
        except Exception as error:
            print(f"Warning: Failed to update note {note.note_id}: {error}")

    return updated_count

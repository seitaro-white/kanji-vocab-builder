"""Construct current vocabulary note payloads without provider or Anki I/O."""

from html import escape
from typing import Any

from kanji_vocab_miner.anki.note_types import (
    VOCAB_NOTE_TYPE_V3,
    VOCAB_TAG,
    VOCAB_V3_FIELDS,
)
from kanji_vocab_miner.enrichment import VocabEnrichment, render_example
from kanji_vocab_miner.kotobank import JapaneseDefinition
from kanji_vocab_miner.vocab_models import PendingVocabItem


def _render_plain_text(value: str) -> str:
    """Escape model-generated plain text and preserve line breaks safely."""
    return escape(value).replace("\n", "<br>")


def prepare_vocab_note(
    item: PendingVocabItem,
    japanese_definition: JapaneseDefinition,
    front: str,
    japanese_cue: str,
    enrichment: VocabEnrichment,
) -> dict[str, Any]:
    """Serialize prepared vocabulary content into the current V3 note payload.

    Older note types remain readable but are not used for new commits. This
    function is the wire-serialization edge, not a provider or Anki operation.

    Args:
        item: Reviewed vocabulary choice and Recall preference. Its word must
            have at least one English definition.
        japanese_definition: Plain Japanese senses and dictionary provenance.
        front: Already-rendered target-word HTML with review-dependent ruby.
        japanese_cue: Already-rendered Japanese-definition HTML, not plain text.
        enrichment: Validated model-generated content. Plain text is escaped;
            the example target is rendered with safe highlighting.

    Returns:
        An AnkiConnect note mapping with modelName, ordered fields, tags and
        duplicate options. It deliberately excludes deckName; the application
        chooses the destination when sending addNote.
    """
    word = item.word
    fields = VOCAB_V3_FIELDS
    return {
        "modelName": VOCAB_NOTE_TYPE_V3,
        "fields": {
            fields["front"]: front,
            fields["back"]: word.definitions[0],
            fields["expression"]: word.expression,
            fields["kana_reading"]: word.kana,
            fields["grammar"]: word.parts_of_speech[0] if word.parts_of_speech else "",
            fields["definition"]: word.definitions[0],
            fields["additional_definitions"]: "\n".join(word.definitions[1:]),
            fields["jlpt"]: f"JLPT N{word.jlpt}" if word.jlpt else "",
            fields["japanese_definition"]: "\n".join(japanese_definition.senses),
            fields["japanese_cue"]: japanese_cue,
            fields["recall"]: "1" if item.recall_enabled else "",
            fields["definition_source"]: japanese_definition.source_name,
            fields["definition_url"]: japanese_definition.source_url,
            fields["nuance"]: _render_plain_text(enrichment.nuance),
            fields["example"]: render_example(enrichment).replace("\n", "<br>"),
            fields["kanji_explanation"]: _render_plain_text(enrichment.kanji_explanation),
        },
        "tags": [VOCAB_TAG],
        "options": {"allowDuplicate": False},
    }

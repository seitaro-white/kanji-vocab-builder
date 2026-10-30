"""Commit reviewed vocabulary through preparation, enrichment, and Anki writes."""

from dataclasses import dataclass

from kanji_vocab_miner.anki import connect as ankiconnect
from kanji_vocab_miner.anki.note_types import VOCAB_DECK_NAME
from kanji_vocab_miner.anki.vocab_notes import prepare_vocab_note
from kanji_vocab_miner.config import (
    AppConfig,
    get_config,
    get_llm_api_key,
    resolve_prompt_path,
)
from kanji_vocab_miner.enrichment import (
    DeepSeekEnrichmentClient,
    VocabEnrichment,
    generate_enrichments,
)
from kanji_vocab_miner.furigana import render_japanese_cue
from kanji_vocab_miner.jisho import fetch_jisho_word_furigana
from kanji_vocab_miner.jmdict import sibling_spellings
from kanji_vocab_miner.kotobank import JapaneseDefinition, KotobankClient
from kanji_vocab_miner.vocab_models import AddFailure, BatchAddResult, PendingVocabItem


@dataclass(frozen=True)
class _PreparedVocabItem:
    """Keep a reviewed row's position alongside its fetched and rendered data."""

    index: int
    item: PendingVocabItem
    definition: JapaneseDefinition
    front: str
    japanese_cue: str


def _create_enrichment_client(config: AppConfig) -> DeepSeekEnrichmentClient | None:
    api_key = get_llm_api_key()
    if api_key is None:
        return None
    return DeepSeekEnrichmentClient(
        api_key=api_key,
        prompt_path=resolve_prompt_path(config.llm.prompt_path),
    )


def _prepare_item(
    index: int,
    item: PendingVocabItem,
    definition_client: KotobankClient,
    reviewed_kanji: set[str],
) -> _PreparedVocabItem | AddFailure:
    try:
        definition = definition_client.lookup(
            item.word.expression,
            candidate_spellings=sibling_spellings(item.word.expression, item.word.kana),
        )
    except Exception as error:
        return AddFailure(item, "definition", str(error))

    try:
        front = fetch_jisho_word_furigana(item.word.expression, reviewed_kanji)
        japanese_cue = render_japanese_cue(definition.senses, reviewed_kanji)
    except Exception as error:
        return AddFailure(item, "furigana", str(error))

    return _PreparedVocabItem(index, item, definition, front, japanese_cue)


def _prepare_items(
    indexed_items: list[tuple[int, PendingVocabItem]],
    definition_client: KotobankClient,
    reviewed_kanji: set[str],
) -> tuple[list[_PreparedVocabItem], list[tuple[int, AddFailure]]]:
    """Return prepared rows and indexed failures from sequential preparation."""
    prepared_items: list[_PreparedVocabItem] = []
    failures: list[tuple[int, AddFailure]] = []
    for index, item in indexed_items:
        prepared = _prepare_item(index, item, definition_client, reviewed_kanji)
        if isinstance(prepared, AddFailure):
            failures.append((index, prepared))
        else:
            prepared_items.append(prepared)
    return prepared_items, failures


def _write_note(
    prepared: _PreparedVocabItem,
    enrichment: VocabEnrichment,
) -> AddFailure | None:
    try:
        note = prepare_vocab_note(
            prepared.item,
            prepared.definition,
            prepared.front,
            prepared.japanese_cue,
            enrichment,
        )
    except Exception as error:
        return AddFailure(prepared.item, "serialization", str(error))

    try:
        ankiconnect.send_request("addNote", note=note | {"deckName": VOCAB_DECK_NAME})
    except Exception as error:
        return AddFailure(prepared.item, "anki", str(error))
    return None


def _enrich_and_write_items(
    prepared_items: list[_PreparedVocabItem],
    enrichment_client: DeepSeekEnrichmentClient,
    concurrency: int,
) -> tuple[list[PendingVocabItem], list[tuple[int, AddFailure]]]:
    """Return added rows and indexed failures after enrichment and ordered writes."""
    if not prepared_items:
        return [], []
    outcomes = generate_enrichments(
        [prepared.item for prepared in prepared_items],
        enrichment_client,
        max_workers=concurrency,
    )
    added: list[PendingVocabItem] = []
    failures: list[tuple[int, AddFailure]] = []
    for prepared, outcome in zip(prepared_items, outcomes):
        if outcome.enrichment is None:
            message = str(outcome.error or "Unknown enrichment failure")
            failure = AddFailure(prepared.item, "enrichment", message)
        else:
            failure = _write_note(prepared, outcome.enrichment)
        if failure is not None:
            failures.append((prepared.index, failure))
        else:
            added.append(prepared.item)
    return added, failures


def add_vocab_items(
    items: list[PendingVocabItem],
    definition_client: KotobankClient | None = None,
    enrichment_client: DeepSeekEnrichmentClient | None = None,
    config: AppConfig | None = None,
) -> BatchAddResult:
    """Commit included rows through preparation, enrichment and ordered writes.

    The caller owns Add filtering, status presentation and pending-state updates.
    Clients may be supplied to bypass provider construction. Failures are returned
    in reviewed order, preserving Recall choices without an unenriched fallback.
    """
    existing_expressions = ankiconnect.get_vocab_expressions()
    result = BatchAddResult(
        skipped_duplicates=[
            item for item in items if item.word.expression in existing_expressions
        ]
    )
    eligible_items = [
        (index, item)
        for index, item in enumerate(items)
        if item.word.expression not in existing_expressions
    ]
    if not eligible_items:
        return result

    app_config = config or get_config()
    if enrichment_client is None:
        enrichment_client = _create_enrichment_client(app_config)
    if enrichment_client is None:
        message = (
            "Missing KANJI_VOCAB_MINER_LLM__API_KEY; set it before "
            "committing vocabulary."
        )
        result.failed = [
            AddFailure(item, "enrichment", message) for _, item in eligible_items
        ]
        return result

    reviewed_kanji = ankiconnect.get_reviewed_kanji()
    prepared_items, preparation_failures = _prepare_items(
        eligible_items, definition_client or KotobankClient(), reviewed_kanji
    )
    result.added, write_failures = _enrich_and_write_items(
        prepared_items, enrichment_client, app_config.llm.concurrency
    )
    result.failed = [
        failure for _, failure in sorted(preparation_failures + write_failures)
    ]
    return result

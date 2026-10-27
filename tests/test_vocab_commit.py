"""Vocabulary commit orchestration with mocked service boundaries."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import create_autospec

import pytest

from kanji_vocab_miner import config as config_module
from kanji_vocab_miner import jisho, vocab_commit
from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.anki.note_types import VOCAB_DECK_NAME
from kanji_vocab_miner.config import AppConfig
from kanji_vocab_miner.enrichment import (
    DeepSeekEnrichmentClient,
    EnrichmentError,
    EnrichmentOutcome,
    VocabEnrichment,
)
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.kotobank import JapaneseDefinition, KotobankClient
from kanji_vocab_miner.vocab_models import PendingVocabItem


def _definition(expression: str) -> JapaneseDefinition:
    return JapaneseDefinition(
        expression=expression,
        senses=[f"{expression}の定義。"],
        source_name="辞書",
        source_url=f"https://example.test/{expression}",
    )


def _enrichment(expression: str) -> VocabEnrichment:
    return VocabEnrichment(
        nuance=f"Nuance for {expression}.",
        example_sentence=f"{expression}を使う。",
        example_target=expression,
        kanji_explanation=f"Kanji for {expression}.",
    )


class FakeEnrichmentClient:
    def __init__(self, failures=None):
        self.failures = failures or {}
        self.calls = []

    def generate(self, word):
        self.calls.append(word.expression)
        if word.expression in self.failures:
            raise EnrichmentError(self.failures[word.expression])
        return _enrichment(word.expression)


def _config(concurrency: int = 5) -> AppConfig:
    return AppConfig(llm={"concurrency": concurrency})


def test_add_vocab_items_fetches_definitions_in_order_for_every_item(monkeypatch) -> None:
    """Recognition-only and recall items both receive sequential definition lookups."""
    items = [
        PendingVocabItem(word=JishoWord(expression="学校", kana="がっこう", jlpt=5, definitions=["school"])),
        PendingVocabItem(
            word=JishoWord(expression="覚える", kana="おぼえる", jlpt=4, definitions=["remember"]),
            recall_enabled=True,
        ),
    ]
    lookups = []
    added_notes = []

    class FakeClient:
        def lookup(self, expression):
            lookups.append(expression)
            return JapaneseDefinition(
                expression=expression,
                senses=[f"{expression}の定義"],
                source_name="デジタル大辞泉",
                source_url=f"https://kotobank.jp/word/{expression}",
            )

    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: {"学"})
    monkeypatch.setattr(
        vocab_commit, "fetch_jisho_word_furigana", lambda expression, reviewed: f"front:{expression}"
    )
    monkeypatch.setattr(
        vocab_commit, "render_japanese_cue", lambda senses, reviewed: f"cue:{senses[0]}"
    )
    monkeypatch.setattr(
        connect,
        "send_request",
        lambda action, **params: added_notes.append(params["note"]),
    )

    result = vocab_commit.add_vocab_items(
        items,
        definition_client=FakeClient(),
        enrichment_client=FakeEnrichmentClient(),
        config=_config(),
    )

    assert lookups == ["学校", "覚える"]
    assert len(result.added) == 2
    assert result.failed == []
    assert added_notes[0]["fields"]["Recall"] == ""
    assert added_notes[1]["fields"]["Recall"] == "1"
    assert all(note["deckName"] == VOCAB_DECK_NAME for note in added_notes)
    assert all(note["modelName"] == "MyJapaneseVocabularyV3" for note in added_notes)


def test_add_vocab_items_preserves_alternate_spelling_through_real_furigana(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Commit 眼鏡 without mocking away the Jisho HTML parsing regression."""
    item = PendingVocabItem(
        JishoWord(expression="眼鏡", kana="めがね", jlpt=5, definitions=["glasses"])
    )
    html = (Path(__file__).parent / "fixtures" / "jisho_megane.html").read_text(
        encoding="utf-8"
    )
    notes: list[dict[str, Any]] = []
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: {"眼"})

    def fetch_page(url: str) -> SimpleNamespace:
        assert url == "https://jisho.org/word/眼鏡"
        return SimpleNamespace(text=html, raise_for_status=lambda: None)

    def capture_note(action: str, **params: Any) -> int:
        assert action == "addNote"
        notes.append(params["note"])
        return 123

    monkeypatch.setattr(jisho.requests, "get", fetch_page)
    monkeypatch.setattr(connect, "send_request", capture_note)
    definition_client = create_autospec(KotobankClient, instance=True)
    definition_client.lookup.side_effect = _definition
    enrichment_client = create_autospec(DeepSeekEnrichmentClient, instance=True)
    enrichment_client.generate.return_value = _enrichment("眼鏡")
    result = vocab_commit.add_vocab_items(
        [item],
        definition_client=definition_client,
        enrichment_client=enrichment_client,
        config=_config(),
    )

    assert result.added == [item]
    assert result.failed == []
    assert result.skipped_duplicates == []
    assert len(notes) == 1
    assert notes[0]["fields"]["Expression"] == "眼鏡"
    assert notes[0]["fields"]["Front"] == "<ruby>眼鏡<rt>めがね</rt></ruby>"
    assert notes[0]["deckName"] == VOCAB_DECK_NAME


def test_add_vocab_items_prepares_native_sudachi_cue_with_mocked_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise real cue generation while keeping every external operation mocked."""
    item = PendingVocabItem(
        word=JishoWord(expression="猫", kana="ねこ", jlpt=5, definitions=["cat"])
    )
    definition = JapaneseDefinition(
        expression="猫",
        senses=[" 国家公務員\r\n\n\n𠮷𠮷 ", "<猫>"],
        source_name="辞書",
        source_url="https://example.test/cat",
    )
    notes: list[dict[str, Any]] = []
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set("国家公務員"))
    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", lambda *args: "jisho-front")

    def capture_note(action: str, **params: Any) -> int:
        assert action == "addNote"
        notes.append(params["note"])
        return 123

    monkeypatch.setattr(connect, "send_request", capture_note)
    result = vocab_commit.add_vocab_items(
        [item],
        definition_client=SimpleNamespace(lookup=lambda expression: definition),
        enrichment_client=FakeEnrichmentClient(),
        config=_config(),
    )

    assert result.added == [item]
    assert result.failed == []
    assert notes[0]["fields"]["Front"] == "jisho-front"
    assert notes[0]["fields"]["JapaneseCue"] == (
        '<div class="sense"> <ruby>国家公務員<rt class="known">こっかこうむいん'
        '</rt></ruby>\r\n\n\n𠮷𠮷 </div><br><div class="sense">'
        '&lt;<ruby>猫<rt>ねこ</rt></ruby>&gt;</div>'
    )


def test_add_vocab_items_classifies_partial_failures_and_duplicates(monkeypatch) -> None:
    """A failed row is retained while later rows still commit successfully."""
    duplicate = PendingVocabItem(word=JishoWord(expression="学校", kana="がっこう", jlpt=5, definitions=["school"]))
    failed = PendingVocabItem(word=JishoWord(expression="不存在", kana="ふそんざい", jlpt=0, definitions=["missing"]))
    added = PendingVocabItem(word=JishoWord(expression="猫", kana="ねこ", jlpt=5, definitions=["cat"]))

    lookups = []

    class FakeClient:
        def lookup(self, expression):
            lookups.append(expression)
            if expression == "不存在":
                raise RuntimeError("definition missing")
            return JapaneseDefinition(
                expression=expression,
                senses=["動物。"],
                source_name="デジタル大辞泉",
                source_url="https://kotobank.jp/word/猫",
            )

    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: {"学校"})
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", lambda *args: "front")
    monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: 42)

    enrichment_client = FakeEnrichmentClient()
    result = vocab_commit.add_vocab_items(
        [duplicate, failed, added],
        definition_client=FakeClient(),
        enrichment_client=enrichment_client,
        config=_config(),
    )

    assert result.skipped_duplicates == [duplicate]
    assert result.added == [added]
    assert len(result.failed) == 1
    assert result.failed[0].item is failed
    assert result.failed[0].stage == "definition"
    assert result.failed[0].message == "definition missing"
    assert lookups == ["不存在", "猫"]
    assert enrichment_client.calls == ["猫"]


@pytest.mark.parametrize(
    ("failing_operation", "expected_stage"),
    [("furigana", "furigana"), ("addNote", "anki")],
)
def test_add_vocab_items_labels_preparation_and_anki_failures(
    monkeypatch, failing_operation, expected_stage
) -> None:
    """Failures after definition lookup retain their actionable stage."""
    item = PendingVocabItem(
        word=JishoWord(
            expression="学校", kana="がっこう", jlpt=5, definitions=["school"]
        )
    )

    class FakeClient:
        def lookup(self, expression):
            return JapaneseDefinition(
                expression=expression,
                senses=["教育を行う所。"],
                source_name="デジタル大辞泉",
                source_url="https://kotobank.jp/word/学校",
            )

    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", lambda *args: "front")
    if failing_operation == "furigana":
        monkeypatch.setattr(
            vocab_commit,
            "render_japanese_cue",
            lambda *args: (_ for _ in ()).throw(RuntimeError("cue failed")),
        )
    else:
        monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")
        monkeypatch.setattr(
            connect,
            "send_request",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("add failed")),
        )

    result = vocab_commit.add_vocab_items(
        [item],
        definition_client=FakeClient(),
        enrichment_client=FakeEnrichmentClient(),
        config=_config(),
    )

    assert result.added == []
    assert len(result.failed) == 1
    assert result.failed[0].stage == expected_stage


def test_add_vocab_items_missing_key_short_circuits_after_duplicates(
    monkeypatch,
) -> None:
    duplicate = PendingVocabItem(
        word=JishoWord(
            expression="既存", kana="きそん", jlpt=0, definitions=["existing"]
        )
    )
    eligible = PendingVocabItem(
        word=JishoWord(
            expression="新規", kana="しんき", jlpt=0, definitions=["new"]
        ),
        recall_enabled=True,
    )
    forbidden_calls = []

    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: {"既存"})
    monkeypatch.setattr(vocab_commit, "get_llm_api_key", lambda: None)
    monkeypatch.setattr(
        connect,
        "get_reviewed_kanji",
        lambda: forbidden_calls.append("reviewed") or set(),
    )
    monkeypatch.setattr(
        vocab_commit,
        "fetch_jisho_word_furigana",
        lambda *args: forbidden_calls.append("jisho"),
    )
    monkeypatch.setattr(
        connect,
        "send_request",
        lambda *args, **kwargs: forbidden_calls.append("anki"),
    )

    class ForbiddenKotobank:
        def lookup(self, expression):
            forbidden_calls.append("kotobank")

    result = vocab_commit.add_vocab_items(
        [duplicate, eligible], definition_client=ForbiddenKotobank(), config=_config()
    )

    assert result.skipped_duplicates == [duplicate]
    assert result.added == []
    assert [failure.item for failure in result.failed] == [eligible]
    assert result.failed[0].stage == "enrichment"
    assert "KANJI_VOCAB_MINER_LLM__API_KEY" in result.failed[0].message
    assert eligible.recall_enabled is True
    assert forbidden_calls == []


@pytest.mark.parametrize("use_explicit_config", [True, False])
def test_add_vocab_items_constructs_enrichment_client_from_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, use_explicit_config: bool
) -> None:
    item = PendingVocabItem(
        JishoWord(
            expression="学校", kana="がっこう", jlpt=5, definitions=["school"]
        )
    )
    prompt_path = tmp_path / "prompt.md"
    constructed = []

    class ConstructedClient:
        def __init__(self, api_key, prompt_path):
            constructed.append((api_key, prompt_path))

        def generate(self, word):
            return _enrichment(word.expression)

    class DefinitionClient:
        def lookup(self, expression):
            return _definition(expression)

    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(vocab_commit, "get_llm_api_key", lambda: "environment-key")
    monkeypatch.setattr(vocab_commit, "DeepSeekEnrichmentClient", ConstructedClient)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", lambda *args: "front")
    monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: 1)

    settings = AppConfig(llm={"prompt_path": prompt_path, "concurrency": 1})
    monkeypatch.setattr(config_module, "_config", settings, raising=False)
    result = vocab_commit.add_vocab_items(
        [item],
        definition_client=DefinitionClient(),
        config=settings if use_explicit_config else None,
    )

    assert constructed == [("environment-key", prompt_path)]
    assert result.added == [item]


def test_add_vocab_items_writes_v3_successes_in_reviewed_order(
    monkeypatch,
) -> None:
    items = [
        PendingVocabItem(
            word=JishoWord(
                expression=expression,
                kana=expression,
                jlpt=0,
                definitions=["meaning"],
            )
        )
        for expression in ["学校", "不存在", "猫", "犬"]
    ]
    added_expressions = []

    class DefinitionClient:
        def lookup(self, expression):
            return _definition(expression)

    def fake_send(action, **params):
        assert action == "addNote"
        assert params["note"]["modelName"] == "MyJapaneseVocabularyV3"
        added_expressions.append(params["note"]["fields"]["Expression"])
        return len(added_expressions)

    enrichment_client = FakeEnrichmentClient(
        failures={"不存在": "generation rejected"}
    )
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(
        vocab_commit,
        "fetch_jisho_word_furigana",
        lambda expression, reviewed: f"front:{expression}",
    )
    monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", fake_send)

    result = vocab_commit.add_vocab_items(
        items,
        definition_client=DefinitionClient(),
        enrichment_client=enrichment_client,
        config=_config(concurrency=2),
    )

    assert added_expressions == ["学校", "猫", "犬"]
    assert result.added == [items[0], items[2], items[3]]
    assert [failure.item for failure in result.failed] == [items[1]]
    assert result.failed[0].stage == "enrichment"
    assert result.failed[0].message == "generation rejected"


def test_add_vocab_items_returns_mixed_failures_in_reviewed_order(
    monkeypatch,
) -> None:
    items = [
        PendingVocabItem(
            word=JishoWord(
                expression=expression,
                kana=expression,
                jlpt=0,
                definitions=[] if expression == "serialization" else ["meaning"],
            )
        )
        for expression in ["definition", "enrichment", "serialization", "furigana", "anki"]
    ]

    class DefinitionClient:
        def lookup(self, expression):
            if expression == "definition":
                raise RuntimeError("definition failed")
            return _definition(expression)

    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())

    def fake_furigana(expression, reviewed):
        if expression == "furigana":
            raise RuntimeError("furigana failed")
        return f"front:{expression}"

    def fake_send(action, **params):
        assert action == "addNote"
        raise RuntimeError("anki failed")

    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", fake_furigana)
    monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", fake_send)

    result = vocab_commit.add_vocab_items(
        items,
        definition_client=DefinitionClient(),
        enrichment_client=FakeEnrichmentClient(
            failures={"enrichment": "enrichment failed"}
        ),
        config=_config(),
    )

    assert [failure.item for failure in result.failed] == items
    assert [failure.stage for failure in result.failed] == [
        "definition",
        "enrichment",
        "serialization",
        "furigana",
        "anki",
    ]


@pytest.mark.parametrize("expressions", [[], ["existing", "another"]])
def test_add_vocab_items_without_eligible_rows_skips_preparation(
    monkeypatch: pytest.MonkeyPatch, expressions: list[str]
) -> None:
    items = [
        PendingVocabItem(
            JishoWord(expression=value, kana="", jlpt=0, definitions=["meaning"])
        )
        for value in expressions
    ]
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set(expressions))

    def forbidden_config() -> None:
        pytest.fail("No eligible rows should require configuration or providers")

    monkeypatch.setattr(vocab_commit, "get_config", forbidden_config)

    result = vocab_commit.add_vocab_items(items)

    assert result.added == []
    assert result.failed == []
    assert result.skipped_duplicates == items


def test_add_vocab_items_finishes_preparation_and_enrichment_before_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [
        PendingVocabItem(
            JishoWord(expression=value, kana="", jlpt=0, definitions=["meaning"])
        )
        for value in ["first", "failed", "last"]
    ]
    operations = []
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")

    def lookup(expression: str) -> JapaneseDefinition:
        operations.append(f"definition:{expression}")
        return _definition(expression)

    def render_front(expression: str, reviewed: set[str]) -> str:
        operations.append(f"furigana:{expression}")
        return "front"

    def generate_out_of_order(
        pending: list[PendingVocabItem],
        client: FakeEnrichmentClient,
        max_workers: int,
    ) -> list[EnrichmentOutcome]:
        assert pending == items
        assert max_workers == 2
        assert operations == [
            "definition:first", "furigana:first",
            "definition:failed", "furigana:failed",
            "definition:last", "furigana:last",
        ]
        for item in reversed(pending):
            operations.append(f"enriched:{item.word.expression}")
        return [
            EnrichmentOutcome(items[0], enrichment=_enrichment("first")),
            EnrichmentOutcome(items[1], error=EnrichmentError("rejected")),
            EnrichmentOutcome(items[2], enrichment=_enrichment("last")),
        ]

    def capture_write(action: str, **params: Any) -> int:
        assert action == "addNote"
        operations.append(f"write:{params['note']['fields']['Expression']}")
        return 1

    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", render_front)
    monkeypatch.setattr(vocab_commit, "generate_enrichments", generate_out_of_order)
    monkeypatch.setattr(connect, "send_request", capture_write)

    result = vocab_commit.add_vocab_items(
        items,
        definition_client=SimpleNamespace(lookup=lookup),
        enrichment_client=FakeEnrichmentClient(),
        config=_config(concurrency=2),
    )

    assert result.added == [items[0], items[2]]
    assert [failure.item for failure in result.failed] == [items[1]]
    assert operations[6:] == [
        "enriched:last", "enriched:failed", "enriched:first",
        "write:first", "write:last",
    ]


def test_add_vocab_items_labels_serialization_failure_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = PendingVocabItem(
        JishoWord(expression="missing definition", kana="", jlpt=0, definitions=[]),
        recall_enabled=True,
    )
    added = PendingVocabItem(
        JishoWord(expression="valid", kana="", jlpt=0, definitions=["meaning"])
    )
    notes = []
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(vocab_commit, "fetch_jisho_word_furigana", lambda *args: "front")
    monkeypatch.setattr(vocab_commit, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(
        connect, "send_request", lambda action, **params: notes.append(params["note"])
    )

    result = vocab_commit.add_vocab_items(
        [failed, added],
        definition_client=SimpleNamespace(lookup=_definition),
        enrichment_client=FakeEnrichmentClient(),
        config=_config(),
    )

    assert result.added == [added]
    assert [(failure.item, failure.stage) for failure in result.failed] == [
        (failed, "serialization")
    ]
    assert failed.recall_enabled is True
    assert [note["fields"]["Expression"] for note in notes] == ["valid"]
    assert [note["modelName"] for note in notes] == ["MyJapaneseVocabularyV3"]

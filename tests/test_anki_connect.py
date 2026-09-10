from datetime import date, datetime
import threading
import time
from types import SimpleNamespace

import pytest
import requests

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.anki.schemas import KanjiCard
from kanji_vocab_miner.config import AppConfig
from kanji_vocab_miner.enrichment import EnrichmentError, VocabEnrichment
from kanji_vocab_miner.review_status import KanjiReviewStatus
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.kotobank import JapaneseDefinition
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


@pytest.mark.integration
def test_ping_anki():
    """
    Test if Anki is running and AnkiConnect is available.

    This basic test ensures that we can connect to the AnkiConnect API.
    All other tests will fail if this one doesn't pass.
    """
    try:
        # Try to get the AnkiConnect API version
        payload = {
            "action": "version",
            "version": 6
        }
        response = requests.post("http://localhost:8765", json=payload)
        response.raise_for_status()

        # Check if we got a valid response
        result = response.json()
        assert "result" in result, "Invalid response from AnkiConnect"
        assert result["result"] >= 6, "AnkiConnect version is too old"

        print(f"Successfully connected to AnkiConnect (version {result['result']})")
    except (requests.RequestException, ConnectionError) as e:
        pytest.fail(f"Failed to connect to Anki: {str(e)}. Make sure Anki is running with AnkiConnect installed.")

@pytest.mark.integration
def test_get_current_card():
    """
    Test getting the current card from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. A card to be currently open in Anki with a "Kanji" field

    Will fail if Anki isn't running or no card is displayed.
    """
    # Get the current card
    card = connect.get_current_card()

    # Assert we got something back
    assert card, "No card returned from get_current_card"

@pytest.mark.integration
def test_get_current_kanji():
    """
    Test getting the current kanji from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. A card to be currently open in Anki with a "Kanji" field

    Will fail if Anki isn't running or no card is displayed.
    """
    # Get the current kanji
    kanjicard = connect.get_current_card()

    # Assert it's not empty
    kanjichar = kanjicard.fields.Kanji.value
    # Unicode ranges for Kanji: CJK Unified Ideographs (4E00-9FFF)
    assert 0x4E00 <= ord(kanjichar) <= 0x9FFF


@pytest.mark.integration
def test_get_reviewed_kanji():
    """
    Test getting all reviewed kanji from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. At least one kanji card to have been reviewed in the deck 'All in one Kanji'

    Will fail if Anki isn't running.
    """
    # Get the reviewed kanji set
    kanji_set = connect.get_reviewed_kanji()

    # Check that we got back a set
    assert len(kanji_set) > 0, "No kanji returned from get_reviewed_kanji"

    # If we got any kanji, check that they look like kanji
    for k in kanji_set:
        assert len(k) == 1, f"Kanji '{k}' is not a single character"
        assert 0x4E00 <= ord(k) <= 0x9FFF, f"Character '{k}' is not a kanji"

    print(f"Successfully retrieved {len(kanji_set)} reviewed kanji")

@pytest.mark.integration
def test_get_reviewed_vocab():
    """
    Test getting all reviewed vocabulary from Anki.

    Requires:
    1. Anki to be running with AnkiConnect installed
    2. At least one vocabulary card to have been reviewed in the deck 'VocabularyNew'

    Will fail if Anki isn't running or no vocab has been reviewed.
    """
    # Get the reviewed vocab list
    vocab_list = connect.get_reviewed_vocab()

    # Check that we got back a list and it's not empty
    assert isinstance(vocab_list, list), "get_reviewed_vocab should return a list"
    assert len(vocab_list) > 0, "No vocabulary returned from get_reviewed_vocab"

    # If we got any vocab, check that they are non-empty strings
    for word in vocab_list:
        assert isinstance(word, str), f"Vocabulary item '{word}' is not a string"
        assert len(word) > 0, "Encountered an empty string in reviewed vocabulary"

    print(f"Successfully retrieved {len(vocab_list)} reviewed vocabulary words")


def test_get_all_kanji_ignores_review_state(monkeypatch):
    """get_all_kanji returns every kanji in the deck, regardless of review state."""
    def fake_send(action, **params):
        if action == "findCards":
            # Must NOT filter by review state — we want the whole deck.
            assert "is:new" not in params["query"]
            return [1, 2, 3]
        if action == "cardsInfo":
            return [
                {"fields": {"Kanji": {"value": "学"}}},
                {"fields": {"Kanji": {"value": "校"}}},
                {"fields": {"Kanji": {"value": "学"}}},  # duplicate collapses in a set
            ]
        raise AssertionError(f"unexpected action {action}")

    monkeypatch.setattr(connect, "send_request", fake_send)
    assert connect.get_all_kanji() == {"学", "校"}


def test_get_kanji_review_status_uses_all_duplicate_cards(monkeypatch):
    """Any duplicate with at least one review makes the kanji reviewed."""
    monkeypatch.setattr(
        connect,
        "get_config",
        lambda: SimpleNamespace(kanji_deck=SimpleNamespace(name="Kanji Deck")),
    )

    def fake_send(action, **params):
        if action == "findCards":
            assert params["query"] == 'deck:"Kanji Deck" "Kanji:学"'
            return [10, 20]
        if action == "cardsInfo":
            assert params["cards"] == [10, 20]
            return [{"reps": 0}, {"reps": 3}]
        raise AssertionError(f"unexpected action {action}")

    monkeypatch.setattr(connect, "send_request", fake_send)

    assert connect.get_kanji_review_status("学") == KanjiReviewStatus.REVIEWED


def test_get_kanji_review_status_distinguishes_new_and_missing(monkeypatch):
    monkeypatch.setattr(
        connect,
        "get_config",
        lambda: SimpleNamespace(kanji_deck=SimpleNamespace(name="Kanji Deck")),
    )
    responses = iter([[10], [{"reps": 0}], []])
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: next(responses))

    assert connect.get_kanji_review_status("新") == KanjiReviewStatus.NOT_REVIEWED
    assert connect.get_kanji_review_status("無") == KanjiReviewStatus.NOT_IN_DECK


def test_count_vocab_notes_added_since_uses_note_creation_dates(monkeypatch):
    def note_id(year, month, day):
        return int(datetime(year, month, day, 12).timestamp() * 1000)

    old_note = note_id(2026, 9, 2)
    first_tracked_note = note_id(2026, 9, 3)
    later_note = note_id(2026, 9, 4)
    def fake_send(action, **params):
        assert action == "findNotes"
        assert params["query"] == f'deck:"{connect.VOCAB_DECK_NAME}"'
        return [old_note, first_tracked_note, later_note, later_note]

    monkeypatch.setattr(connect, "send_request", fake_send)

    assert connect.count_vocab_notes_added_since(date(2026, 9, 3)) == 2


@pytest.fixture
def kanji_card_with_restore():
    """
    Yields (card_id, original_due) for a known kanji card and restores its
    due value after the test, so Anki's queue order is not permanently changed.
    """
    card_id = connect.find_kanji_card_id("使")
    assert card_id is not None, "Could not find kanji card for 使 — is the deck loaded?"
    info = connect.send_request("cardsInfo", cards=[card_id])
    original_due = info[0]["due"]
    yield card_id, original_due
    connect.send_request("setSpecificValueOfCard", card=card_id, keys=["due"], newValues=[original_due])


@pytest.mark.integration
def test_reposition_card_to_top(kanji_card_with_restore):
    """Test that reposition_card_to_top moves a card to due=0 in its queue."""
    card_id, original_due = kanji_card_with_restore
    connect.reposition_card_to_top(card_id)
    info = connect.send_request("cardsInfo", cards=[card_id])
    assert info[0]["due"] == 0


@pytest.mark.integration
def test_reposition_restores_correctly(kanji_card_with_restore):
    """Sanity check: the fixture restore actually works (due goes back to original)."""
    card_id, original_due = kanji_card_with_restore
    connect.reposition_card_to_top(card_id)
    # Teardown will restore — we just verify it was moved during the test
    info = connect.send_request("cardsInfo", cards=[card_id])
    assert info[0]["due"] == 0
    assert original_due != 0  # Confirm the card wasn't already at 0


@pytest.mark.integration
def test_find_kanji_card_id_returns_none_for_unknown():
    """Test that find_kanji_card_id returns None for a character not in the deck."""
    result = connect.find_kanji_card_id("X")
    assert result is None


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
        connect, "fetch_jisho_word_furigana", lambda expression, reviewed: f"front:{expression}"
    )
    monkeypatch.setattr(
        connect, "render_japanese_cue", lambda senses, reviewed: f"cue:{senses[0]}"
    )
    monkeypatch.setattr(
        connect,
        "send_request",
        lambda action, **params: added_notes.append(params["note"]),
    )

    result = connect.add_vocab_items(
        items,
        client=FakeClient(),
        enrichment_client=FakeEnrichmentClient(),
        config=_config(),
    )

    assert lookups == ["学校", "覚える"]
    assert len(result.added) == 2
    assert result.failed == []
    assert added_notes[0]["fields"]["Recall"] == ""
    assert added_notes[1]["fields"]["Recall"] == "1"
    assert all(note["deckName"] == connect.VOCAB_DECK_NAME for note in added_notes)
    assert all(note["modelName"] == "MyJapaneseVocabularyV3" for note in added_notes)


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
    monkeypatch.setattr(connect, "fetch_jisho_word_furigana", lambda *args: "front")
    monkeypatch.setattr(connect, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: 42)

    enrichment_client = FakeEnrichmentClient()
    result = connect.add_vocab_items(
        [duplicate, failed, added],
        client=FakeClient(),
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
    monkeypatch.setattr(connect, "fetch_jisho_word_furigana", lambda *args: "front")
    if failing_operation == "furigana":
        monkeypatch.setattr(
            connect,
            "render_japanese_cue",
            lambda *args: (_ for _ in ()).throw(RuntimeError("cue failed")),
        )
    else:
        monkeypatch.setattr(connect, "render_japanese_cue", lambda *args: "cue")
        monkeypatch.setattr(
            connect,
            "send_request",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("add failed")),
        )

    result = connect.add_vocab_items(
        [item],
        client=FakeClient(),
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
    monkeypatch.setattr(connect, "get_llm_api_key", lambda: None)
    monkeypatch.setattr(
        connect,
        "get_reviewed_kanji",
        lambda: forbidden_calls.append("reviewed") or set(),
    )
    monkeypatch.setattr(
        connect,
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

    result = connect.add_vocab_items(
        [duplicate, eligible], client=ForbiddenKotobank(), config=_config()
    )

    assert result.skipped_duplicates == [duplicate]
    assert result.added == []
    assert [failure.item for failure in result.failed] == [eligible]
    assert result.failed[0].stage == "enrichment"
    assert "KANJI_VOCAB_MINER_LLM__API_KEY" in result.failed[0].message
    assert eligible.recall_enabled is True
    assert forbidden_calls == []


def test_add_vocab_items_constructs_enrichment_client_from_config(
    monkeypatch, tmp_path
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
    monkeypatch.setattr(connect, "get_llm_api_key", lambda: "environment-key")
    monkeypatch.setattr(connect, "DeepSeekEnrichmentClient", ConstructedClient)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(connect, "fetch_jisho_word_furigana", lambda *args: "front")
    monkeypatch.setattr(connect, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: 1)

    result = connect.add_vocab_items(
        [item],
        client=DefinitionClient(),
        config=AppConfig(llm={"prompt_path": prompt_path, "concurrency": 1}),
    )

    assert constructed == [("environment-key", prompt_path)]
    assert result.added == [item]


def test_add_vocab_items_enriches_concurrently_but_writes_v3_in_reviewed_order(
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
        for expression in ["slow", "failed", "fast", "later"]
    ]
    added_expressions = []

    class ConcurrentClient:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def generate(self, word):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(
                    {"slow": 0.04, "failed": 0.02}.get(
                        word.expression, 0.005
                    )
                )
                if word.expression == "failed":
                    raise EnrichmentError("generation rejected")
                return _enrichment(word.expression)
            finally:
                with self.lock:
                    self.active -= 1

    class DefinitionClient:
        def lookup(self, expression):
            return _definition(expression)

    def fake_send(action, **params):
        assert action == "addNote"
        assert params["note"]["modelName"] == "MyJapaneseVocabularyV3"
        added_expressions.append(params["note"]["fields"]["Expression"])
        return len(added_expressions)

    enrichment_client = ConcurrentClient()
    monkeypatch.setattr(connect, "get_vocab_expressions", lambda: set())
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(
        connect,
        "fetch_jisho_word_furigana",
        lambda expression, reviewed: f"front:{expression}",
    )
    monkeypatch.setattr(connect, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", fake_send)

    result = connect.add_vocab_items(
        items,
        client=DefinitionClient(),
        enrichment_client=enrichment_client,
        config=_config(concurrency=2),
    )

    assert enrichment_client.max_active == 2
    assert added_expressions == ["slow", "fast", "later"]
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
                definitions=["meaning"],
            )
        )
        for expression in ["definition", "enrichment", "furigana", "anki"]
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

    monkeypatch.setattr(connect, "fetch_jisho_word_furigana", fake_furigana)
    monkeypatch.setattr(connect, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", fake_send)

    result = connect.add_vocab_items(
        items,
        client=DefinitionClient(),
        enrichment_client=FakeEnrichmentClient(
            failures={"enrichment": "enrichment failed"}
        ),
        config=_config(),
    )

    assert [failure.item for failure in result.failed] == items
    assert [failure.stage for failure in result.failed] == [
        "definition",
        "enrichment",
        "furigana",
        "anki",
    ]


def test_add_vocab_items_progress_has_one_terminal_event_per_input(
    monkeypatch,
) -> None:
    duplicate = PendingVocabItem(
        JishoWord(expression="duplicate", kana="", jlpt=0, definitions=["x"])
    )
    failed = PendingVocabItem(
        JishoWord(expression="failed", kana="", jlpt=0, definitions=["x"])
    )
    added = PendingVocabItem(
        JishoWord(expression="added", kana="", jlpt=0, definitions=["x"])
    )
    events = []

    class DefinitionClient:
        def lookup(self, expression):
            if expression == "failed":
                raise RuntimeError("missing")
            return _definition(expression)

    monkeypatch.setattr(
        connect, "get_vocab_expressions", lambda: {"duplicate"}
    )
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(connect, "fetch_jisho_word_furigana", lambda *args: "front")
    monkeypatch.setattr(connect, "render_japanese_cue", lambda *args: "cue")
    monkeypatch.setattr(connect, "send_request", lambda *args, **kwargs: 1)

    connect.add_vocab_items(
        [duplicate, failed, added],
        client=DefinitionClient(),
        enrichment_client=FakeEnrichmentClient(),
        on_progress=events.append,
        config=_config(),
    )

    terminal_events = [event for event in events if event.is_terminal]
    assert [event.completed for event in terminal_events] == [1, 2, 3]
    assert [event.item for event in terminal_events] == [duplicate, failed, added]
    assert [event.outcome for event in terminal_events] == [
        "duplicate",
        "failed",
        "added",
    ]
    assert all(event.total == 3 for event in events)
    assert any(
        event.phase == "enrichment" and not event.is_terminal
        for event in events
    )


def test_sync_vocab_furigana_updates_front_and_cue_once_per_note(monkeypatch) -> None:
    """Furigana sync writes all changed V2 fields in one note update."""
    calls = []

    def fake_send(action, **params):
        calls.append((action, params))
        if action == "findNotes":
            return [10]
        if action == "notesInfo":
            return [
                {
                    "noteId": 10,
                    "fields": {
                        "Front": {"value": "<ruby>学校<rt>がっこう</rt></ruby>"},
                        "JapaneseCue": {"value": "<ruby>教育<rt>きょういく</rt></ruby>"},
                        "JapaneseDefinition": {"value": "教育を行う所。"},
                    },
                }
            ]
        if action == "updateNote":
            return None
        raise AssertionError(action)

    monkeypatch.setattr(connect, "send_request", fake_send)
    monkeypatch.setattr(connect, "get_reviewed_kanji", lambda: {"学", "校", "教", "育"})

    assert connect.sync_vocab_furigana() == 1
    update = [params for action, params in calls if action == "updateNote"]
    assert update == [
        {
            "note": {
                "id": 10,
                "fields": {
                    "Front": '<ruby>学校<rt class="known">がっこう</rt></ruby>',
                    "JapaneseCue": '<ruby>教育<rt class="known">きょういく</rt></ruby>',
                },
            }
        }
    ]


def test_get_vocab_expressions_reads_unique_note_fields(monkeypatch) -> None:
    """Duplicate detection reads Expression once per note across model types."""
    calls = []

    def fake_send(action, **params):
        calls.append((action, params))
        if action == "findNotes":
            return [10, 20, 30]
        return [
            {"fields": {"Expression": {"value": "学校"}}},
            {"fields": {"Expression": {"value": "学校"}}},
            {"fields": {"Front": {"value": "legacy malformed"}}},
        ]

    monkeypatch.setattr(connect, "send_request", fake_send)

    assert connect.get_vocab_expressions() == {"学校"}
    assert calls == [
        ("findNotes", {"query": 'deck:"KanjiVocabMiner-Vocabulary"'}),
        ("notesInfo", {"notes": [10, 20, 30]}),
    ]


def test_prepare_note_v2_builds_exact_recognition_only_payload() -> None:
    """V2 serialization includes Japanese provenance even when Recall is blank."""
    item = PendingVocabItem(
        word=JishoWord(
            expression="学校",
            kana="がっこう",
            jlpt=5,
            definitions=["school", "educational institution"],
            parts_of_speech=["Noun"],
        )
    )
    definition = JapaneseDefinition(
        expression="学校",
        senses=["教育を行う所。", "学びを得る場所。"],
        source_name="デジタル大辞泉",
        source_url="https://kotobank.jp/word/学校",
    )

    note = connect.prepare_note_v2(
        item,
        definition,
        front="<ruby>学校<rt>がっこう</rt></ruby>",
        japanese_cue='<div class="sense">教育を行う所。</div>',
    )

    assert note == {
        "modelName": "MyJapaneseVocabularyV2",
        "fields": {
            "Front": "<ruby>学校<rt>がっこう</rt></ruby>",
            "Back": "school",
            "Expression": "学校",
            "Kana Reading": "がっこう",
            "Grammar": "Noun",
            "Definition": "school",
            "Additional Definitions": "educational institution",
            "JLPT": "JLPT N5",
            "JapaneseDefinition": "教育を行う所。\n学びを得る場所。",
            "JapaneseCue": '<div class="sense">教育を行う所。</div>',
            "Recall": "",
            "DefinitionSource": "デジタル大辞泉",
            "DefinitionURL": "https://kotobank.jp/word/学校",
        },
        "tags": ["kanji-vocab-miner"],
        "options": {"allowDuplicate": False},
    }


@pytest.mark.integration
def test_prepare_note():
    """
    Test the prepare_note function for creating Anki note data.
    This test relies on the live functionality of `fetch_jisho_word_furigana`
    called within `prepare_note`.
    """
    # 1. Test with a standard word
    sample_word_full = JishoWord(
        expression="日本語",
        kana="にほんご",
        jlpt=3,
        definitions=["Japanese language", "The spoken and written language of Japan."],
        parts_of_speech=["Noun", "Proper Noun"]
    )

    # Call prepare_note - this will internally call fetch_jisho_word_furigana
    prepared_note_full = connect.prepare_note(sample_word_full, set())

    # Define expected output, assuming fetch_jisho_word_furigana("日本語", set()) -> "<ruby>日本語<rt>にほんご</rt></ruby>"
    expected_note_full = {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": "<ruby>日本語<rt>にほんご</rt></ruby>",
            "Back": "Japanese language",
            "Expression": "日本語",
            "Kana Reading": "にほんご",
            "Grammar": "Noun",
            "Definition": "Japanese language",
            "Additional Definitions": "The spoken and written language of Japan.",
            "JLPT": "JLPT N3",
        },
        "tags": ["kanji-vocab-miner"],
        "options": {"allowDuplicate": False},
    }
    assert prepared_note_full == expected_note_full

    # 2. Test with minimal definitions and parts_of_speech (single items)
    sample_word_minimal = JishoWord(
        expression="学ぶ",
        kana="まなぶ",
        jlpt=4,
        definitions=["to learn"],
        parts_of_speech=["Verb"]
    )
    prepared_note_minimal = connect.prepare_note(sample_word_minimal, set())

    # Define expected output, assuming fetch_jisho_word_furigana("学ぶ", set()) -> "<ruby>学<rt>まな</rt></ruby>ぶ"
    expected_note_minimal = {
        "modelName": "MyJapaneseVocabulary",
        "fields": {
            "Front": "<ruby>学<rt>まな</rt></ruby>ぶ",
            "Back": "to learn",
            "Expression": "学ぶ",
            "Kana Reading": "まなぶ",
            "Grammar": "Verb",
            "Definition": "to learn",
            "Additional Definitions": "",  # Expect empty string if only one definition
            "JLPT": "JLPT N4",
        },
        "tags": ["kanji-vocab-miner"],
        "options": {"allowDuplicate": False},
    }
    assert prepared_note_minimal == expected_note_minimal


def test_prepare_note_v3_builds_exact_safe_payload() -> None:
    from kanji_vocab_miner.enrichment import VocabEnrichment

    item = PendingVocabItem(
        word=JishoWord(
            expression="学校", kana="がっこう", jlpt=5,
            definitions=["school", "institution"], parts_of_speech=["Noun"]
        ), recall_enabled=True,
    )
    definition = JapaneseDefinition(
        expression="学校", senses=["教育を行う所。"], source_name="辞書",
        source_url="https://example.test/学校",
    )
    enrichment = VocabEnrichment(
        nuance='Formal & useful\n"context"',
        example_sentence="私は<学校>へ行く。",
        example_target="学校",
        kanji_explanation="学ぶ & 校舎\n組み合わせ",
    )

    note = connect.prepare_note_v3(item, definition, "front", "cue", enrichment)

    assert note["modelName"] == "MyJapaneseVocabularyV3"
    assert list(note["fields"]) == [
        "Front", "Back", "Expression", "Kana Reading", "Grammar", "Definition",
        "Additional Definitions", "JLPT", "JapaneseDefinition", "JapaneseCue",
        "Recall", "DefinitionSource", "DefinitionURL", "Nuance", "Example",
        "KanjiExplanation",
    ]
    assert note["fields"]["Nuance"] == "Formal &amp; useful<br>&quot;context&quot;"
    assert note["fields"]["Example"] == (
        "私は&lt;<strong class=\"example-target\">学校</strong>&gt;へ行く。"
    )
    assert note["fields"]["KanjiExplanation"] == "学ぶ &amp; 校舎<br>組み合わせ"

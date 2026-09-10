"""Tests for structured DeepSeek vocabulary enrichment."""

import json
from pathlib import Path
import threading
import time

import pytest
import requests

from kanji_vocab_miner.enrichment import (
    DeepSeekEnrichmentClient,
    EnrichmentError,
    VocabEnrichment,
    generate_enrichments,
    render_example,
)
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.vocab_models import PendingVocabItem


class FakeResponse:
    def __init__(self, payload=None, *, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def word() -> JishoWord:
    return JishoWord(
        expression="開く",
        kana="ひらく",
        jlpt=4,
        definitions=["to open", "to hold an event"],
        parts_of_speech=["Godan verb", "transitive verb"],
    )


def valid_data(**overrides):
    data = {
        "nuance": "Used when opening something or beginning access.",
        "example_sentence": "窓を開いた。",
        "example_target": "開いた",
        "kanji_explanation": "開 conveys opening and く is okurigana.",
    }
    data.update(overrides)
    return data


def envelope(data=None):
    return {
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(data or valid_data())}
                ],
            },
        ]
    }


def make_client(tmp_path: Path, responses, **kwargs):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Editable content guidance", encoding="utf-8")
    transport = FakeTransport(responses)
    sleeps = []
    client = DeepSeekEnrichmentClient(
        "top-secret",
        prompt,
        transport=transport,
        sleeper=sleeps.append,
        **kwargs,
    )
    return client, transport, sleeps


def test_render_example_highlights_first_raw_target_before_escaping() -> None:
    enrichment = VocabEnrichment(
        nuance="Used for literal and figurative openings.",
        example_sentence="&amp; と & を比べる。& を選ぶ。",
        example_target="&",
        kanji_explanation="No kanji applies.",
    )

    assert render_example(enrichment) == (
        '<strong class="example-target">&amp;</strong>'
        "amp; と &amp; を比べる。&amp; を選ぶ。"
    )


def test_generate_sends_structured_primary_sense_request(tmp_path) -> None:
    client, transport, _ = make_client(tmp_path, [FakeResponse(envelope())])

    result = client.generate(word())

    assert result == VocabEnrichment(**valid_data())
    url, request = transport.calls[0]
    assert url == "https://api.deepseek.com/responses"
    assert request["headers"]["Authorization"] == "Bearer top-secret"
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["timeout"] == 30.0
    body = request["json"]
    assert body["model"] == "deepseek-flash"
    assert "Contract requirements:" in body["instructions"]
    assert "example_target" in body["instructions"]
    assert "register, connotation" not in body["instructions"]
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["name"] == "vocab_enrichment"
    assert body["text"]["format"]["schema"]["additionalProperties"] is False
    assert "Editable content guidance" in body["input"]
    assert "Expression: 開く" in body["input"]
    assert "Kana reading: ひらく" in body["input"]
    assert "Primary definition: to open" in body["input"]
    assert "Primary part of speech: Godan verb" in body["input"]
    assert "to hold an event" not in body["input"]
    assert "transitive verb" not in body["input"]


@pytest.mark.parametrize(
    "bad_response",
    [
        requests.ConnectionError("top-secret network failure"),
        FakeResponse(status_error=requests.HTTPError("Bearer top-secret denied")),
        FakeResponse({"output": []}),
        FakeResponse(ValueError("top-secret invalid envelope")),
        FakeResponse({"output_text": "not json"}),
        FakeResponse({"output_text": json.dumps({"nuance": "only one field"})}),
        FakeResponse(envelope(valid_data(nuance="   "))),
        FakeResponse(envelope(valid_data(example_target="閉じた"))),
    ],
)
def test_generate_retries_invalid_results_and_sanitizes_error(
    tmp_path, bad_response
) -> None:
    client, transport, sleeps = make_client(
        tmp_path, [bad_response, bad_response, bad_response]
    )

    with pytest.raises(EnrichmentError) as exc_info:
        client.generate(word())

    assert len(transport.calls) == 3
    assert sleeps == [0.25, 0.5]
    assert "top-secret" not in str(exc_info.value)
    assert "after 3 attempts" in str(exc_info.value)
    assert "Correction:" in transport.calls[1][1]["json"]["input"]


def test_generate_stops_after_later_success(tmp_path) -> None:
    client, transport, sleeps = make_client(
        tmp_path,
        [FakeResponse({"output": []}), FakeResponse(envelope())],
    )

    assert client.generate(word()).example_target == "開いた"
    assert len(transport.calls) == 2
    assert sleeps == [0.25]


def test_generate_accepts_top_level_output_text(tmp_path) -> None:
    response = FakeResponse({"output_text": json.dumps(valid_data())})
    client, _, _ = make_client(tmp_path, [response])

    assert client.generate(word()).nuance.startswith("Used when")


def test_generate_enrichments_is_bounded_ordered_and_failure_isolated() -> None:
    items = [
        PendingVocabItem(
            JishoWord(
                expression=expression,
                kana=expression,
                jlpt=0,
                definitions=["meaning"],
            )
        )
        for expression in ["slow", "fail", "fast", "later"]
    ]

    class ControlledClient:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def generate(self, input_word):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep({"slow": 0.04, "fail": 0.02}.get(input_word.expression, 0.005))
                if input_word.expression == "fail":
                    raise EnrichmentError("expected failure")
                return VocabEnrichment(**valid_data(nuance=input_word.expression))
            finally:
                with self.lock:
                    self.active -= 1

    client = ControlledClient()
    completed = []

    outcomes = generate_enrichments(
        items, client, max_workers=2, on_complete=completed.append
    )

    assert [outcome.item for outcome in outcomes] == items
    assert [outcome.enrichment.nuance if outcome.enrichment else None for outcome in outcomes] == [
        "slow",
        None,
        "fast",
        "later",
    ]
    assert isinstance(outcomes[1].error, EnrichmentError)
    assert client.max_active == 2
    assert sorted(item.word.expression for item in completed) == [
        "fail",
        "fast",
        "later",
        "slow",
    ]

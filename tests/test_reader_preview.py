"""Offline examples exercise native output without enforcing human lexical splits."""

import json
import re
import runpy
from html import unescape
from pathlib import Path

import pytest
import requests
from bs4 import BeautifulSoup

from kanji_vocab_miner.article_reader import analyze_article
from kanji_vocab_miner.article_render import render_article_html

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads(
    (ROOT / "tests/fixtures/reader_annotation_draft.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["id"])
def test_native_reader_preserves_reviewed_passages(case: dict) -> None:
    tokens = analyze_article(case["source"], set(CORPUS["known_vocabulary"]))
    rendered = render_article_html(tokens, set(CORPUS["known_kanji"]))
    # BeautifulSoup collapses whitespace-only text nodes; inspect raw markup here.
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered)
    assert unescape(re.sub(r"<[^>]+>", "", without_readings)) == case["source"]
    reconstructed = "".join(t.leading_whitespace + t.surface for t in tokens)
    assert reconstructed == case["source"]
    for token in tokens:
        if token.surface:
            assert case["source"][token.start:token.end] == token.surface


def test_native_preview_is_standalone_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Preview must not access Anki or external services")

    monkeypatch.setattr(requests, "post", forbidden)
    preview = runpy.run_path(str(ROOT / "scripts/preview_sudachi_reader.py"))
    html = preview["render_native_preview"](CORPUS)
    parsed = BeautifulSoup(html, "html.parser")

    assert parsed.find("link", rel="stylesheet") is None
    assert parsed.find("script", src=True) is None
    assert "SudachiPy 0.6.11" in parsed.get_text()
    assert "SudachiDict-core 20260428" in parsed.get_text()
    assert len(parsed.select("#native-boundaries section")) == 9
    assert parsed.article.select(".name-person") != []
    assert parsed.article.select(".name-place") != []
    assert parsed.article.find("b") is None
    assert "mock" in parsed.get_text()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("食べました", ["食べ", "まし", "た"]),
        ("具体的な", ["具体的", "な"]),
        ("子供っぽい", ["子供", "っぽい"]),
        ("申込受付期間", ["申込", "受付期間"]),
    ],
)
def test_pinned_native_boundaries_are_explicit(
    source: str, expected: list[str]
) -> None:
    """Small reviewed snapshots of the pinned engine, not a homemade parser oracle."""
    assert [token.surface for token in analyze_article(source, set())] == expected

"""Validate human annotation integrity independently of native Sudachi boundaries."""

import json
import runpy
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads(
    (ROOT / "tests/fixtures/reader_annotation_draft.json").read_text(encoding="utf-8")
)
PREVIEW = runpy.run_path(str(ROOT / "scripts/preview_reader_annotations.py"))


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["id"])
def test_annotation_spans_cover_original_text_exactly(case: dict) -> None:
    """No omitted endings, doubled characters, or silently normalized source text."""
    assert "".join(segment["text"] for segment in case["segments"]) == case["source"]
    for segment in case["segments"]:
        if "ruby" in segment:
            assert "".join(base for base, _ in segment["ruby"]) == segment["text"]
            for base, reading in segment["ruby"]:
                assert base != ""
                assert reading is None or reading != ""
        if "lookup" in segment:
            assert segment["lookup"] != ""
            assert PREVIEW["KANJI"].search(segment["text"]) is not None


def test_preview_renders_each_original_passage_losslessly() -> None:
    """Removing ruby readings leaves every original source character unchanged."""
    html = PREVIEW["render_preview"](CORPUS)
    parsed = BeautifulSoup(html, "html.parser")
    for case in CORPUS["cases"]:
        passage = parsed.find(id=case["id"]).find(class_="passage")
        for reading in passage.find_all("rt"):
            reading.decompose()
        assert passage.get_text() == case["source"]
    assert parsed.find("b") is None  # Literal <b> in the source must not be markup.


def test_preview_uses_kanji_not_vocabulary_to_classify_ruby() -> None:
    """Mock-known vocab can need ruby; mock-unknown vocab can have known kanji."""
    parsed = BeautifulSoup(PREVIEW["render_preview"](CORPUS), "html.parser")
    words = parsed.find(id="independent-knowledge").find_all(class_="word")
    library = next(word for word in words if "図書館" in word.get("title", ""))
    student = next(word for word in words if "学生" in word.get("title", ""))
    assert "known-vocab" in library["class"]
    assert library.rt.get("class", []) == []
    assert "unknown-vocab" in student["class"]
    assert student.rt["class"] == ["known-kanji"]


def test_corpus_preserves_review_status_and_case_ids_are_unique() -> None:
    """Human lexical spans remain distinct from the accepted native parser policy."""
    assert CORPUS["status"] == "reviewed-reading-intent"
    assert CORPUS["boundary_policy"] == "native-sudachi-c-accepted"
    assert CORPUS["version"] == 1
    ids = [case["id"] for case in CORPUS["cases"]]
    assert len(ids) == len(set(ids))

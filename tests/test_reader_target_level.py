"""Reader target-level policy, including the actual CSS visibility selectors."""

import re
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from kanji_vocab_miner.article_reader import analyze_article
from kanji_vocab_miner.article_render import render_article_html
from kanji_vocab_miner.web import create_demo_app


@pytest.mark.parametrize("target_level", [5, 4, 3, 2, 1])
@pytest.mark.parametrize("word_level", [5, 4, 3, 2, 1, None])
@pytest.mark.parametrize("is_known", [False, True])
@pytest.mark.parametrize("has_known_kanji", [False, True])
@pytest.mark.parametrize("mode", ["unknown", "all", "none"])
def test_target_level_visibility_matrix(
    target_level: int,
    word_level: int | None,
    is_known: bool,
    has_known_kanji: bool,
    mode: str,
) -> None:
    token = replace(
        analyze_article("学生", set())[0],
        jlpt_level=word_level,
        is_known=is_known,
    )
    html = render_article_html([token], set("学生") if has_known_kanji else set())
    soup = BeautifulSoup(
        f'<article class="furigana-mode-{mode}" '
        f'data-target-level="{target_level}">{html}</article>',
        "html.parser",
    )
    css_path = Path(__file__).resolve().parents[1] / "kanji_vocab_miner/static/article_reader.css"
    css = re.sub(r"/\*.*?\*/", "", css_path.read_text(), flags=re.DOTALL)
    # Evaluate the real stylesheet selectors in cascade order, rather than
    # duplicating its list of harder levels in a test-only implementation.
    is_visible = True
    for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        display = re.search(r"\bdisplay:\s*(none|ruby-text)\s*;", declarations)
        if display and soup.rt in soup.select(selector.strip()):
            is_visible = display.group(1) != "none"

    needs_support = not is_known and (
        word_level is None or word_level < target_level
    )
    expected = mode == "all" or (
        mode == "unknown" and (not has_known_kanji or needs_support)
    )
    assert is_visible is expected
    assert soup.span.get("data-reading-level") == (
        str(word_level or 0) if not is_known else None
    )


def test_target_level_control_defaults_to_n2() -> None:
    client = create_demo_app().test_client()
    response = client.post("/", data={"text": "学生"})
    soup = BeautifulSoup(response.data, "html.parser")
    control = soup.select_one("#target-level")
    assert soup.select_one('label[for="target-level"]') is not None
    assert [option["value"] for option in control.select("option")] == [
        "5", "4", "3", "2", "1"
    ]
    assert control.select_one("option[selected]")["value"] == "2"
    assert soup.article["data-target-level"] == "2"
    assert soup.select_one("#furigana-help") is not None


def test_names_and_grammar_do_not_gain_vocabulary_reading_metadata() -> None:
    soup = BeautifulSoup(
        render_article_html(analyze_article("山田さんは東京都で食べました", set())),
        "html.parser",
    )
    assert all(not name.has_attr("data-reading-level") for name in soup.select(".name"))
    supported = soup.select("[data-reading-level]")
    assert len(supported) == 1
    assert "食" in supported[0].get_text()

"""Generate an offline preview of the real Sudachi reader and its native boundaries.

Run: uv run python scripts/preview_sudachi_reader.py
Human annotations remain separate: differences are shown, not silently corrected.
"""

import argparse
import json
from html import escape
from importlib.metadata import version
from pathlib import Path

from kanji_vocab_miner.article_reader import analyze_article
from kanji_vocab_miner.web import create_app

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/reader_annotation_draft.json"


def render_native_preview(corpus: dict) -> str:
    """Render the actual Flask reader with explicit, offline mock inventories."""
    cases = corpus["cases"] + [
        {
            "title": "Additional derived forms (native boundaries)",
            "source": "国際化、安全性、研究者、子供っぽい。山田さんは東京都へ行く。",
            "segments": [],
        }
    ]
    source = "\n\n".join(case["source"] for case in cases)
    app = create_app(
        expression_loader=lambda: set(corpus["known_vocabulary"]),
        known_loader=set,
        kanji_loader=lambda: set(corpus["known_kanji"]),
    )
    app.config["READER_DEMO"] = True
    response = app.test_client().post("/", data={"text": source})
    if response.status_code != 200:
        raise RuntimeError("Could not render the offline Sudachi preview")
    html = response.get_data(as_text=True)
    # Embed trusted local assets so the generated file works without a server.
    assets = ROOT / "kanji_vocab_miner/static"
    css = (assets / "article_reader.css").read_text(encoding="utf-8")
    javascript = (assets / "article_reader.js").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="/static/article_reader.css">',
        f"<style>{css}</style>",
    ).replace(
        '<script src="/static/article_reader.js" defer></script>',
        f"<script>{javascript}</script>",
    ).replace('<a href="/" class="start-over">Start Over</a>', "")
    sections = []
    for case in cases:
        tokens = analyze_article(case["source"], set())
        native = " / ".join(token.surface for token in tokens if token.surface)
        human = " / ".join(
            segment["text"] for segment in case["segments"] if "lookup" in segment
        )
        rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{escape(value)}</td>"
                for value in (
                    token.surface,
                    token.identities[0] if token.identities else "",
                    token.reading or "—",
                    token.part_of_speech.category if token.part_of_speech else "",
                    token.name_kind or "",
                )
            )
            + "</tr>"
            for token in tokens
            if token.surface
        )
        sections.append(
            f'<section><h3>{escape(case["title"])}</h3>'
            f'<p><strong>Native C-mode tokens:</strong> {escape(native)}</p>'
            '<p><strong>Human lexical spans (not a parser contract):</strong> '
            f'{escape(human) or "—"}</p>'
            '<details><summary>Native readings, dictionary forms and tags</summary>'
            '<table><thead><tr><th>Surface</th><th>Dictionary form</th><th>Reading</th>'
            f'<th>POS</th><th>Name kind</th></tr></thead><tbody>{rows}</tbody></table>'
            '</details></section>'
        )
    report = (
        '<section id="native-boundaries"><h2>Native Sudachi baseline</h2>'
        f'<p>SudachiPy {escape(version("sudachipy"))}; '
        f'SudachiDict-core {escape(version("sudachidict-core"))}; C mode.</p>'
        '<p>Readings and boundaries below are native parser output, not guarantees of '
        'the intended interpretation. In particular, 市場 is read しじょう here, '
        'where the human example intended いちば. Inflections can remain split. '
        'No custom grouping or name dictionary was added.</p>'
        + "".join(sections)
        + '</section>'
    )
    return html.replace("</main>", f"{report}</main>")


def main() -> None:
    """Write a standalone preview with no Anki or user-inventory access."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/reader-sudachi-preview.html"
    )
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_native_preview(corpus), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

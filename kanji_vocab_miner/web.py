"""Flask boundary for the localhost furigana article reader."""

import argparse
from collections.abc import Callable

from flask import Flask, render_template, request
from markupsafe import Markup

from kanji_vocab_miner.anki.connect import get_reviewed_kanji, get_vocab_expressions
from kanji_vocab_miner.article_reader import (
    analyze_article,
    build_unknown_vocabulary_summary,
)
from kanji_vocab_miner.article_render import render_article_html
from kanji_vocab_miner.known_words import load_known_words


def load_reader_known_kanji() -> set[str]:
    """Load reviewed kanji strictly, without masking Anki failures as empty data."""
    return get_reviewed_kanji(should_raise=True)


def create_app(
    expression_loader: Callable[[], set[str]] = get_vocab_expressions,
    known_loader: Callable[[], set[str]] = load_known_words,
    kanji_loader: Callable[[], set[str]] = load_reader_known_kanji,
) -> Flask:
    """Create the reader with separately injectable vocabulary and kanji loaders."""
    app = Flask(__name__)
    # 50,000 supplementary characters need ~600KB when URL-encoded, exceeding
    # Flask's default 500KB form limit even though the article itself is valid.
    app.config["MAX_FORM_MEMORY_SIZE"] = 1_000_000

    @app.route("/", methods=["GET", "POST"])
    def index() -> tuple[str, int] | str:
        source_text = (
            request.form.get("text", "")
            if request.method == "POST"
            else app.config.get("READER_INITIAL_TEXT", "")
        )
        if request.method == "POST":
            if not source_text.strip():
                error = "Paste some Japanese text before submitting."
            elif len(source_text) > 50_000:
                error = "Articles must stay within the 50,000-character limit."
            else:
                error = None
            if error:
                return (
                    render_template(
                        "article_reader.html",
                        source_text=source_text,
                        error=error,
                    ),
                    400,
                )
            try:
                anki_expressions = expression_loader()
                known_kanji = kanji_loader()
            except Exception:
                app.logger.exception("Could not load Anki knowledge inventories")
                return (
                    render_template(
                        "article_reader.html",
                        source_text=source_text,
                        error=(
                            "Start Anki and make sure AnkiConnect is enabled, "
                            "then retry."
                        ),
                    ),
                    503,
                )
            try:
                known_vocabulary = anki_expressions | known_loader()
                analyzed_tokens = analyze_article(source_text, known_vocabulary)
                article_html = render_article_html(analyzed_tokens, known_kanji)
                unknown_vocabulary_groups = build_unknown_vocabulary_summary(
                    analyzed_tokens
                )
            except Exception:
                app.logger.exception("Could not process article")
                return (
                    render_template(
                        "article_reader.html",
                        source_text=source_text,
                        error=(
                            "Could not process this article. Check local reader "
                            "configuration and installed dictionaries (uv sync), then retry."
                        ),
                    ),
                    500,
                )
            return render_template(
                "article_reader.html",
                article_html=Markup(article_html),
                unknown_vocabulary_groups=unknown_vocabulary_groups,
            )
        return render_template("article_reader.html", source_text=source_text)

    return app


def create_demo_app() -> Flask:
    """Create an explicitly offline reader with the annotation mock inventories."""
    app = create_app(
        expression_loader=lambda: {"学校", "図書館", "食べる", "経済的"},
        known_loader=set,
        kanji_loader=lambda: set("学校食見日人本大生"),
    )
    app.config.update(
        READER_DEMO=True,
        READER_INITIAL_TEXT=(
            "学校の図書館で、学生が日本語の本を見た。昼ご飯を食べました。\n\n"
            "山田さんは東京都に住んでいる。情報処理と人工知能を学んでいる。\n"
            "具体的な説明。国際化、安全性、研究者、子供っぽい。"
        ),
    )
    return app


def main() -> None:
    """Run a localhost reader; --demo uses mock knowledge and never calls Anki."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo", action="store_true", help="Use offline mock inventories"
    )
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    app = create_demo_app() if args.demo else create_app()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()

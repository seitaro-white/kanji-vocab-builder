"""Flask boundary for the localhost furigana article reader."""

from collections.abc import Callable

from flask import Flask, render_template, request
from markupsafe import Markup

from kanji_vocab_miner.anki.connect import get_vocab_expressions
from kanji_vocab_miner.article_reader import (
    analyze_article,
    build_unknown_dictionary,
    render_article_html,
)
from kanji_vocab_miner.known_words import load_known_words


def create_app(
    expression_loader: Callable[[], set[str]] = get_vocab_expressions,
    known_loader: Callable[[], set[str]] = load_known_words,
) -> Flask:
    """Create the article reader application with injectable vocabulary loaders."""
    app = Flask(__name__)

    @app.route("/", methods=["GET", "POST"])
    def index() -> tuple[str, int] | str:
        source_text = request.form.get("text", "")
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
            except Exception:
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
                tokens = analyze_article(source_text, known_vocabulary)
                article_html = render_article_html(tokens)
                dictionary_groups = build_unknown_dictionary(tokens)
            except Exception:
                return (
                    render_template(
                        "article_reader.html",
                        source_text=source_text,
                        error="Could not process this article. Please retry.",
                    ),
                    500,
                )
            return render_template(
                "article_reader.html",
                article_html=Markup(article_html),
                dictionary_groups=dictionary_groups,
            )
        return render_template("article_reader.html", source_text=source_text)

    return app

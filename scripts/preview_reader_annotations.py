"""Render the manual reader corpus without the production parser or live Anki.

Run: uv run python scripts/preview_reader_annotations.py
This preview is an annotation review aid, not a proposed tokenizer implementation.
"""

import argparse
import json
import re
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/reader_annotation_draft.json"
KANJI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f]")


def render_segment(segment: dict[str, Any], corpus: dict[str, Any]) -> str:
    """Render a human-selected span; never infer boundaries or readings."""
    if "ruby" not in segment:
        content = escape(segment["text"])
    else:
        chunks = []
        for base, reading in segment["ruby"]:
            if reading is None:
                chunks.append(escape(base))
                continue
            represented = KANJI.findall(base)
            known = bool(represented) and all(
                character in corpus["known_kanji"] for character in represented
            )
            css = ' class="known-kanji"' if known else ""
            chunks.append(
                f"<ruby>{escape(base)}<rt{css}>{escape(reading)}</rt></ruby>"
            )
        content = "".join(chunks)
    if "lookup" not in segment:
        return content
    known = segment["lookup"] in corpus["known_vocabulary"]
    status = "known-vocab" if known else "unknown-vocab"
    label = f"{segment['lookup']} — {'known' if known else 'unknown'} vocabulary"
    return (
        f'<span class="word {status}" title="{escape(label, quote=True)}">'
        f"{content}</span>"
    )


def render_preview(corpus: dict[str, Any]) -> str:
    """Build an offline page from explicit annotations, independent of runtime."""
    sections = []
    for case in corpus["cases"]:
        annotated = "".join(render_segment(s, corpus) for s in case["segments"])
        boundaries = " / ".join(
            f"{s['text']} → {s['lookup']}"
            for s in case["segments"]
            if "lookup" in s
        )
        sections.append(
            f'<section id="{escape(case["id"], quote=True)}">'
            f'<h2>{escape(case["title"])}</h2>'
            f'<p>{escape(case["note"])}</p>'
            f'<p class="passage" lang="ja">{annotated}</p>'
            '<details><summary>Original text and exact proposed lookup spans</summary>'
            f'<p class="source" lang="ja">{escape(case["source"])}</p>'
            f'<p lang="ja">{escape(boundaries)}</p></details></section>'
        )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reader annotations — reviewed reading intent</title>
<style>
body { max-width: 68rem; margin: auto; padding: 1.5rem; color: #17212b;
       background: #f5f7fa; font: 1rem/1.6 system-ui, sans-serif; }
h1, h2 { line-height: 1.3; }
section { background: white; padding: 1rem 1.5rem; margin: 1.5rem 0; border-radius: .5rem; }
.controls { position: sticky; top: 0; background: #e7edf4; padding: .8rem; z-index: 1; }
label { display: inline-block; margin-right: 1rem; }
.passage { font-size: 1.5rem; line-height: 2.8; white-space: pre-wrap; }
.source { white-space: pre-wrap; }
.word { border-radius: .15rem; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
.unknown-vocab { background: #ffeb9c; }
.known-vocab { border-bottom: 2px solid #3274ad; }
.show-known .known-vocab { background: #cce7ff; }
.boundaries .word { outline: 1px solid #78818b; outline-offset: 1px; }
rt { font-size: .55em; }
rt.known-kanji { display: none; }
.all-ruby rt.known-kanji { display: ruby-text; }
.no-ruby rt { display: none !important; }
</style></head><body class="boundaries">
<h1>Reader annotations: reviewed reading intent</h1>
<p>The user reviewed these examples, then accepted native Sudachi boundaries where
those differ. This page preserves the original human annotations, not a strict parser
contract. See <a href="reader-sudachi-preview.html">the actual Sudachi reader preview</a>
for native output and comparisons.</p>
<p>These are manually chosen examples, not output from the current reader. Yellow =
unknown vocabulary; blue underline = known vocabulary. Thin outlines show proposed
word boundaries. Hover a word for its lookup form. Colours are <strong>not JLPT levels</strong>:
we are reviewing boundaries first, independently of JLPT-list coverage.</p>
<p>Default ruby depends only on the mock known-kanji set, never vocabulary status.
For an inseparable kanji group, retain its complete reading if any kanji is unknown.
Kana inside a kanji-containing word can be coloured; standalone kana is plain.</p>
""" + (
        f'<p><strong>Mock known kanji:</strong> {escape(corpus["known_kanji"])}<br>'
        '<strong>Mock known vocabulary:</strong> '
        f'{escape(", ".join(corpus["known_vocabulary"]))}</p>'
    ) + """
<div class="controls" aria-label="Preview options">
<label><input type="checkbox" data-class="all-ruby"> Show all furigana</label>
<label><input type="checkbox" data-class="no-ruby"> Hide all furigana</label>
<label><input type="checkbox" data-class="show-known"> Colour known vocabulary</label>
<label><input type="checkbox" data-class="boundaries" checked> Outline word boundaries</label>
</div>
<p>Original annotations and notes below are retained for provenance. Native Sudachi
now decides lexical boundaries; names use dotted underlines only where its POS tags
identify a person or place. The yellow/blue demonstration colours on this page are
not the production reader's JLPT palette.</p>
""" + "".join(sections) + """
<script>
document.querySelectorAll('[data-class]').forEach(input => {
  input.addEventListener('change', () => {
    document.body.classList.toggle(input.dataset.class, input.checked);
  });
});
</script></body></html>
"""


def main() -> None:
    """Generate a standalone HTML preview that requires no server or services."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/reader-annotation-draft.html")
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_preview(corpus), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

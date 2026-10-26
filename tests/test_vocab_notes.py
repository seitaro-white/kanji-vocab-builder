"""Current vocabulary note serialization and safe enrichment rendering."""

from kanji_vocab_miner.anki import vocab_notes
from kanji_vocab_miner.enrichment import VocabEnrichment
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.kotobank import JapaneseDefinition
from kanji_vocab_miner.vocab_models import PendingVocabItem


def test_prepare_vocab_note_builds_exact_recognition_only_payload() -> None:
    """New notes include all V3 fields even when Recall is blank."""
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

    enrichment = VocabEnrichment(
        nuance="A place of formal education.",
        example_sentence="学校へ行く。",
        example_target="学校",
        kanji_explanation="学 relates to learning and 校 to school.",
    )

    note = vocab_notes.prepare_vocab_note(
        item,
        definition,
        front="<ruby>学校<rt>がっこう</rt></ruby>",
        japanese_cue='<div class="sense">教育を行う所。</div>',
        enrichment=enrichment,
    )

    assert note == {
        "modelName": "MyJapaneseVocabularyV3",
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
            "Nuance": "A place of formal education.",
            "Example": '<strong class="example-target">学校</strong>へ行く。',
            "KanjiExplanation": "学 relates to learning and 校 to school.",
        },
        "tags": ["kanji-vocab-miner"],
        "options": {"allowDuplicate": False},
    }


def test_prepare_vocab_note_escapes_enrichment_and_enables_recall() -> None:
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

    note = vocab_notes.prepare_vocab_note(item, definition, "front", "cue", enrichment)

    assert note["modelName"] == "MyJapaneseVocabularyV3"
    assert set(note["fields"]) == {
        "Front", "Back", "Expression", "Kana Reading", "Grammar", "Definition",
        "Additional Definitions", "JLPT", "JapaneseDefinition", "JapaneseCue",
        "Recall", "DefinitionSource", "DefinitionURL", "Nuance", "Example",
        "KanjiExplanation",
    }
    assert note["fields"]["Recall"] == "1"
    assert note["fields"]["Nuance"] == "Formal &amp; useful<br>&quot;context&quot;"
    assert note["fields"]["Example"] == (
        "私は&lt;<strong class=\"example-target\">学校</strong>&gt;へ行く。"
    )
    assert note["fields"]["KanjiExplanation"] == "学ぶ &amp; 校舎<br>組み合わせ"

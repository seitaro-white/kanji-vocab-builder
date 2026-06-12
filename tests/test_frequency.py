"""Tests for the JMdict frequency-band index (reads jamdict's bundled DB)."""

from kanji_vocab_miner import frequency


def test_build_frequency_index_maps_surface_to_band():
    index = frequency.build_frequency_index()

    assert isinstance(index, dict)
    assert len(index) > 10000  # tens of thousands of ranked forms

    # 日本 carries nf25 in KanjiDic2/JMdict.
    assert index["日本"] == 25

    # All bands are integers in the valid nf range.
    sample = list(index.values())[:1000]
    assert all(isinstance(b, int) and 1 <= b <= 48 for b in sample)


def test_build_frequency_index_takes_min_band_per_surface():
    # When a surface form appears with multiple nf bands, the smallest (most
    # frequent) must win. 国 appears as 国/國; the common form is highly ranked.
    index = frequency.build_frequency_index()
    assert index["国"] <= 5


def test_band_label():
    assert frequency.band_label(None) == ""  # no band -> blank
    assert frequency.band_label(1) == "top 500"
    assert frequency.band_label(2) == "top 1k"
    assert frequency.band_label(5) == "top 2.5k"
    assert frequency.band_label(48) == "top 24k"


def test_words_in_band_returns_expression_kana_definition():
    words = frequency.words_in_band(1)  # nf01 == top 500

    assert len(words) > 100  # a band holds up to ~500 entries
    # Every entry has the three display fields populated.
    for w in words[:20]:
        assert w.expression and w.kana and w.definition

    # The band's surface forms all sit in band 1 of the frequency index.
    index = frequency.build_frequency_index()
    sample = words[0]
    assert index.get(sample.expression) == 1 or index.get(sample.kana) == 1


def test_words_in_band_empty_for_out_of_range():
    assert frequency.words_in_band(0) == []
    assert frequency.words_in_band(99) == []

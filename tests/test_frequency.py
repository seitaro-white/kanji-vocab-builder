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

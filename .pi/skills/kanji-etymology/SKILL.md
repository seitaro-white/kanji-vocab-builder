---
name: kanji-etymology
description: Explains a kanji's etymology, radical (部首), component structure, phonetic and semantic elements, historical form, and readings, then gives a mnemonic. Use when the user asks about a kanji's etymology, radicals, components, origins, reading, or wants a mnemonic.
---

# Kanji Etymology & Radicals

Given a kanji, produce a sourced etymology with a structured radical breakdown and a mnemonic. **Always look the kanji up—never answer from memory.**

## Fast lookup procedure

1. **Do not begin with `web_search`.** Fetch the character's Wiktionary pages directly, preferably in parallel:
   - `https://en.wiktionary.org/wiki/<kanji>`
   - `https://ja.wiktionary.org/wiki/<kanji>`
2. Use English Wiktionary primarily for **Glyph origin**, IDS decomposition (⿰/⿱), radical, stroke count, historical forms, phonetic series, and Old Chinese reconstructions.
3. Use Japanese Wiktionary for Japanese readings, meanings, and Japanese terminology. If it adds nothing useful, do not pad the answer with it.
4. This direct Wiktionary lookup is sufficient by default. **Do not run broad searches merely to collect more citations.**
5. Use one targeted secondary lookup only when:
   - Wiktionary lacks or contradicts the needed etymology;
   - it explicitly presents disputed analyses;
   - a specific claim needs stronger verification; or
   - the user requests deeper cross-checking.
   Prefer a direct page from 漢典/《説文解字》, ctext.org, 漢字ペディア, or コトバンク. Use `web_search` only if the correct direct page cannot be located otherwise.
6. State genuine uncertainty or disagreement explicitly rather than silently choosing an analysis. Cite only pages actually fetched or read; never imply that search-result snippets were inspected as full sources.

## Analysis steps

1. **Radical (部首)**: identify the Kangxi radical, its number, its **Japanese name** (つち, くにがまえ, おおがい, こざとへん, etc.), and total stroke count.
2. **Decompose**: break the kanji into visible components. For each major component, give its Japanese component/radical name where one exists. Add useful sub-components, but do not force folk decompositions that conflict with the historical form.
3. **Classify**: 形声 (phono-semantic), 会意 (ideographic compound), 象形 (pictograph), or 指事 (indicator).
4. **Semantic component**: identify which part carries meaning and explain the connection.
5. **Phonetic component**: identify which part carries sound. Note the phonetic series and Old Chinese reconstruction when Wiktionary supplies them. Explain where the on'yomi comes from, especially when the visible shape is not the historical phonetic. When modern readings no longer resemble one another, explain that the relationship existed at an earlier Chinese stage.
6. **旧字体/新字体**: note relevant traditional, simplified, or variant forms and explain changes affecting the visible analysis.

## Output format

```text
<kanji>  [on'yomi / kun'yomi]  "core meaning"

STRUCTURE:
├─ <component>  <Japanese name> (meaning)   部首 #NN  SEMANTIC
└─ <component>  <Japanese name> (meaning)   PHONETIC ・ <reading>
   └─ <sub-components, only when useful>

ETYMOLOGY: <形声/会意/象形/指事>
<2–3 concise sentences: meaning component, sound component and reading,
historical form or source disagreement where relevant>

MNEMONIC: <one vivid image based on the visible components, with a sound hook if useful>

SOURCES:
- <name>: <direct URL actually consulted>
```

Example for 固:

```text
固  [コ / かた・かたい]  "firm, solid"

STRUCTURE:
├─ 囗  くにがまえ (enclosure)   部首 #31  SEMANTIC
└─ 古  ふるい (old; = 十 + 口)  PHONETIC ・ コ

ETYMOLOGY: 形声—古 supplies the historical sound behind コ, while 囗
contributes enclosure: something shut firmly inside becomes fixed or solid.

MNEMONIC: trap the old (古) thing inside the enclosure (囗)—now it is 固い,
locked down tight.
```

## Mnemonic guidance

- Build the mnemonic from what is visibly present and use Japanese component names when useful.
- Never present the mnemonic's visual decomposition as the true etymology unless the sources support it.
- If the phonetic is visually misleading, prioritize the picture; a sound hook is optional.
- Keep it to one vivid sentence. Give a second variant only when the first is weak.

## Rules

- Never guess; fetch Wiktionary directly before answering.
- Keep routine lookups fast: no broad web search and no unnecessary source tour.
- Always include definitions, on/kun readings, structure, classification, etymology, mnemonic, and direct source links.
- Distinguish visible composition, dictionary radical, and historical derivation.
- If the user asks why a reading or radical occurs, answer that question directly.

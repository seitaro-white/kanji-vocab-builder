---
name: kanji-etymology
description: Explains a kanji's etymology, radical (部首), component structure, phonetic and semantic elements, historical form, and readings, then gives a mnemonic. Use when the user asks about a kanji's etymology, radicals, components, origins, reading, or wants a mnemonic.
---

# Kanji Etymology & Radicals

Given a kanji, produce a sourced etymology with a structured radical breakdown and a mnemonic. **Always look the kanji up—never answer from memory.**

## Fast lookup procedure

1. Fetch the character's Wiktionary and wanikani pages directly, preferably in parallel:
   - `https://ja.wiktionary.org/wiki/<kanji>`
   - `https://www.wanikani.com/kanji/<kanji>`
2. Use Japanese Wiktionary for radicals, Japanese readings, meanings, and Japanese terminology.
3. Use Wanikani for the alternative wanikani radicals
4. If a component (especially the phonetic or semantic part) itself needs explaining—its own OC reconstruction, readings, or decomposition—fetch that component's own Wiktionary page (e.g. 奇 for 寄) rather than stopping at the parent character's page.


## Analysis steps

1. **Radical (部首)**: identify the radical, its number, its **Japanese name** (つち, くにがまえ, おおがい, こざとへん, etc.), and total stroke count.
2. **Decompose**: break the kanji into visible components. For each major component, give its Japanese component/radical name where one exists. Add useful sub-components, but do not force folk decompositions that conflict with the historical form.
2. **Semantic component**: identify which part carries meaning and explain the connection.
5. **Phonetic component**: identify which part carries sound. Note the phonetic series and Old Chinese reconstruction when Wiktionary supplies them. Explain where the on'yomi comes from, especially when the visible shape is not the historical phonetic. When modern readings no longer resemble one another, explain that the relationship existed at an earlier Chinese stage.
6. **旧字体/新字体**: note relevant traditional, simplified, or variant forms and explain changes affecting the visible analysis.

## Output format

```text
<kanji>  [on'yomi / kun'yomi]  "core meaning"


```RADICAL STRUCTURE
├─ <component>  <Japanese name> (meaning)   部首 #NN  SEMANTIC
└─ <component>  <Japanese name> (meaning)   PHONETIC ・ <reading>
   └─ <sub-components, only when useful>
```


```WANIKANI RADICALS
├─ <component>
└─ <component>
   └─ <sub-components, only when useful>
```

ETYMOLOGY:
<2–3 concise sentences: meaning component, sound component and reading,
historical form or source disagreement where relevant, explained in plain english>

WANIKANI MNEMONIC: The primary wanikani provided

```

Example for 固:

```text
固  [コ / かた・かたい]  "firm, solid"


```RADICAL STRUCTURE
├─ 囗  くにがまえ (enclosure)   部首 #31  SEMANTIC
└─ 古  ふるい (old; = 十 + 口)  PHONETIC ・ コ
```


```WANIKANI RADICALS
├─ <component>
└─ <component>
   └─ <sub-components, only when useful>
```


ETYMOLOGY: 古 supplies the historical sound behind コ, while 囗
contributes enclosure: something shut firmly inside becomes fixed or solid.

WANIKANI MNEMONIC: trap the old (古) thing inside the enclosure (囗)—now it is 固い,
locked down tight.
```

## Rules

- Never guess; fetch Wiktionary directly before answering.
- Always include definitions, on/kun readings, structure, classification, etymology, mnemonic, and direct source links.
- Distinguish visible composition, dictionary radical, and historical derivation.
- If the user asks why a reading or radical occurs, answer that question directly.

# Main concept

I want to replace the current system that generates front-and-back anki vocab cards with JP and english definitions with a new type of card that can be optionally switched between recall only recognition (ie jp -> english) and recognition + recall (also definition -> vocab), with a definition that comes from a japanese dictionary.

### Current behaviour
Adding a vocab card to anki generates a note with 2 cards, jp to en and en to jp. jp to en is useful, en to jp is increasingly becoming tricky as there are lots of synonyms/overlapping words, and I also don't need to be able to recall all of them. The english definitions that come from jisho are also somewhat lacking when it comes to en to jp.

### User stories. 
As a user, I: 
- Want, on the addition of a new vocab word, to be able to choose in the CLI whether to add that word as a one-way recognition only or a 2 way recognise + recall word
- Want to be able to see a japanese to english definition that we have now for recog, but a japanese cue to japanese word for recall (therefore, for each card we need the japanese word, an english dictionary def and a japanese dictionary def)
- Want to be able to keep my existing cards/notes in my anki deck but start adding new cards from this point onwards with a new card template that allows for this new workflow
- Want the japanese cue for each word to have kanji review-dependent furigana generated above as we have right now for the vocab itself
- Have the new template be organised in such a way that I can turn off the recall card on or off by editing the card somehow e.g. with a conditional field


### Requirements 
This will likely require:
- A new module similar to the current JP one that connects to https://kotobank.jp/ to source japanese definitions. it should add maybe just the first and second def available
- A new anki card/note template that we can add to our existing vocab deck going foward. Ideally this new template can be forwards-compatiable with the old vocab type, so we can convert old vocab types into new ones if we want going forward
- Updates to the Anki API connectors to make sure it can generate the new type of card/note, and also be able to read both new and old types of notes for checking what has already been reviewed etc etc
- An extention of the furigana update code to cover the Japanese cue field as well as the current kanji field
- An update to the current "commit list" TUI (currently a single add/forget whether to add the vocab, this should now have an additional field, off by default which we can toggle for each word to decide whether to make it pure recognition or a recall card as well. 
-

### Future features.
Not to worry about for now but in future we add in an LLM feature to generate a better JP cue for each word rather than just the raw dictionary definition from kotobank

### UX flow
Ideally similar to now, i.e. 
- Vocab listed -> added -> at commit list, toggle both add or not and add recall or not (two separate keys to manage this) -> vocab added on commit -> fugigana on everything updated as before


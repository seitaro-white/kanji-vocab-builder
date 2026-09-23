## Feature - better card backmatter for recognition backside of the card

# Current behaviour/issue
right now, the back of the recog cards simply show the dictionary pulled english definition, which is often just a handful of words. This is quite annoying as we don't get the nuance of the meaning or an example. It would be good to use an LLM to generate better backcard material instead. 

## User stories
As a user, I want:
- A "nuance" translation below the simple word dictionary definition, a sentence in english that explains the meaning of the word in terms of how/where it is it be used beyond a simple word translation
- A example sentence below the nuance translation - a fairly simple and short japanese sentence demonstrating how the word is used. The word itself should be in red font and bolded
- A "why those Kanji" explanation that shows the constituent kanji and why those combined together confers the meaning it does for the word
- The ability to alter the prompt that goes to the LLM to tailor what sort of result comes back. Ideally the LLM needs to return a structured output (basically a field for each of the three above) that can be validated, but otherwise the prompt can be tweaked to adjust what sort of output we get for each one

## Implementation.
We probably need another new v3 template (having just moved to v2) with these new fields - no need to migrate over old ones, but something we can start doing from here on out. The LLM called can just go to deepseek-fash for now which I have api and credits for. The prompt I hhave for word explainer now in skills is quite similar to the informaton I want - basically we are just moving it from something generated on the fly from pi to auto-generated for all new vocab we add. 

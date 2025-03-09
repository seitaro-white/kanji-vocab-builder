Below is an outline/plan for creating a command-line tool in Python using the `click` library to interact with Anki (via AnkiConnect) and Jisho (via its API). The plan includes the overall approach, file structure, and a breakdown of responsibilities for each `.py` file. This structure will help you modularize the code and make it easier to implement step-by-step, either manually or with GitHub Copilot.

---

### Project Overview
The CLI tool will:
- Fetch the current Kanji card from Anki's "All in one Kanji" deck via AnkiConnect.
- Query Jisho for words containing that Kanji, sort them based on review status and JLPT level.
- Present a numbered list to the user, allow selection, and add selected words to the "VocabularyNew" deck.

### Tools and Libraries
- **Python**: Base language.
- **Click**: For building the CLI with commands and user input handling.
- **requests**: For making HTTP requests to AnkiConnect (localhost:8765) and Jisho API.
- **json**: For parsing API responses.
- **urllib.parse**: For URL-encoding the Kanji in Jisho API requests.

### File Structure
```
jisho_anki_tool/
├── README.md                # Documentation for setup and usage
├── requirements.txt         # List of dependencies (click, requests)
├── setup.py                 # Optional: For packaging the tool
├── tests/                   # New: Directory for unit tests
│   ├── __init__.py          # Marks directory as a package
│   ├── test_anki_connect.py # Tests for AnkiConnect interactions
│   ├── test_jisho_api.py    # Tests for Jisho API interactions
│   ├── test_card_processor.py # Tests for sorting and processing logic
│   └── test_utils.py        # Tests for utility functions
├── jisho_anki_tool/
│   ├── __init__.py          # Marks directory as a package
│   ├── cli.py              # Main CLI entry point using Click
│   ├── anki_connect.py     # Functions to interact with AnkiConnect API
│   ├── jisho_api.py        # Functions to interact with Jisho API
│   ├── card_processor.py   # Logic for sorting and processing word lists
│   └── utils.py            # Helper functions (e.g., furigana formatting)
```

---

### Detailed Plan

#### 1. **Main CLI Entry Point (`cli.py`)**
- **Responsibility**: Define the CLI interface using `click`, handle user input, and orchestrate the workflow.
- **Outline**:
  - Use `@click.command()` to create a main command (e.g., `jisho-anki`).
  - Run an infinite loop to accept user input (`n` or integers for word selection).
  - When `n` is entered:
    - Call `anki_connect.get_current_card()` to fetch the Kanji.
    - Pass the Kanji to `jisho_api.search_words()` to get a list of words.
    - Pass the word list to `card_processor.sort_and_limit_words()` to sort and limit to 10 words.
    - Display the numbered list to the user.
  - When integers are entered:
    - Parse the input (e.g., "1 3 5") into a list of indices.
    - Pass the selected words to `anki_connect.add_words_to_deck()`.
  - Exit on a special command (e.g., `q` for quit).
- **Notes**:
  - Use `click.echo()` for output to ensure compatibility with Click.
  - Handle invalid input gracefully (e.g., non-existent indices).

#### 2. **AnkiConnect Interaction (`anki_connect.py`)**
- **Responsibility**: Communicate with AnkiConnect API running on `localhost:8765`.
- **Outline**:
  - Define `get_current_card()`:
    - Send a POST request to `http://localhost:8765` with action `"guiCurrentCard"`.
    - Extract the Kanji from the `fields["Front"]["value"]` of the response (assuming "Front" is the field name for Kanji in "All in one Kanji" deck).
    - Return the Kanji string.
  - Define `add_words_to_deck(selected_words)`:
    - For each selected word, create a note with:
      - Deck: `"VocabularyNew"`.
      - Front: Word in Kanji/hiragana/katakana with furigana in `<ruby>` tags (formatted via `utils.format_furigana()`).
      - Back: Top 3 definitions joined with `<br>` tags.
    - Send a POST request with action `"addNotes"` and the list of notes.
- **Notes**:
  - Assume AnkiConnect is running locally (no authentication needed).
  - Validate deck existence or create it if missing (optional).

#### 3. **Jisho API Interaction (`jisho_api.py`)**
- **Responsibility**: Query Jisho API and parse the response.
- **Outline**:
  - Define `search_words(kanji)`:
    - Construct URL: `https://jisho.org/api/v1/search/words?keyword={kanji}` (URL-encode the Kanji).
    - Send GET request using `requests`.
    - Parse JSON response, extracting:
      - Word (Kanji or kana form).
      - Furigana (reading).
      - JLPT level (if present).
      - Definitions (top 3 senses).
      - Other Kanji in the word (for sorting logic).
    - Return a list of dictionaries with this data.
- **Notes**:
  - Filter out results that don’t contain the target Kanji.
  - Handle cases where JLPT level is missing (treat as "common word").

#### 4. **Card Processing Logic (`card_processor.py`)**
- **Responsibility**: Sort and limit the word list based on review status and JLPT level.
- **Outline**:
  - Define `sort_and_limit_words(words, kanji)`:
    - Fetch reviewed Kanji from Anki using `anki_connect.get_reviewed_kanji()` (helper function).
    - For each word:
      - Check if other Kanji in the word (excluding the target Kanji) are in the reviewed set.
      - Assign a priority score: reviewed Kanji (1), unreviewed Kanji (0).
      - Assign JLPT rank: N5 (5), N4 (4), N3 (3), N2 (2), N1 (1), none (0).
    - Sort by:
      1. Reviewed Kanji priority (descending).
      2. JLPT rank (descending).
    - Limit to 10 words and return the sorted list.
  - Define helper `get_reviewed_kanji()` in `anki_connect.py`:
    - Query AnkiConnect with action `"findCards"` for deck `"All in one Kanji"` and filter by reviewed status.
    - Extract Kanji from card fields and return a set.
- **Notes**:
  - Use a stable sort to preserve JLPT order within reviewed/unreviewed groups.

#### 5. **Utility Functions (`utils.py`)**
- **Responsibility**: Handle formatting and helper logic.
- **Outline**:
  - Define `format_furigana(word, reading)`:
    - If the word is in kana only, return it as-is.
    - If Kanji is present, use `<ruby>` tags: `<ruby>kanji<rt>reading</rt></ruby>`.
    - Handle multi-Kanji words by splitting and aligning readings (simplified approach: assume Jisho provides aligned readings).
  - Define `parse_selection(input_str)`:
    - Split input string (e.g., "1 3 5") into a list of integers.
    - Validate indices and return the list.
- **Notes**:
  - Furigana alignment might require approximation; refine based on Jisho response format.

#### 6. **Setup and Documentation**
- **requirements.txt**:
  ```
  click==8.1.7
  requests==2.31.0
  ```
- **README.md**:
  - Instructions to install dependencies (`pip install -r requirements.txt`).
  - How to run the tool (`python -m jisho_anki_tool.cli`).
  - Prerequisites: Anki running with AnkiConnect installed.

---

### Workflow Summary
1. User runs the CLI: `jisho-anki`.
2. User types `n`:
   - Fetches current Kanji from Anki.
   - Queries Jisho for words.
   - Sorts and displays 10 words (e.g., `1. 学校 (N5, reviewed)`, `2. 学生 (N4, reviewed)`, etc.).
3. User types `1 3 5`:
   - Adds words at indices 1, 3, 5 to "VocabularyNew" deck with formatted front/back cards.
4. Repeat or quit with `q`.

---

### Next Steps
You can take this plan and:
- Write the code yourself, starting with `cli.py` to set up the loop and input handling.
- Use GitHub Copilot by feeding it each file’s responsibility and outline, prompting it to generate the code step-by-step.
- Test incrementally (e.g., test AnkiConnect first with a simple query).

Let me know if you’d like clarification on any part or help refining the plan further!
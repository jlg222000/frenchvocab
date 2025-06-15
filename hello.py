"""
I imported: (1) "requests" in order to retrieve contents from French websites and APIs (to gather words,
and definitions)
(2) "random" in order to choose random elements (e.g., words, so that vocab lists don't just generate
the first words in alphabetical order, creating lists with only words that start with "a"
(3) "time" in order to avoid overloading servers or getting blocked on APIs
(4) "re" in order to use regular expressions for pattern  matching
 in order to clean and process the French text for better vocabulary extraction
 (5) "Counter" in order to look at word frequencies (I'm focused on advanced words that appear less often)
 (6) "urljoin" in order to ensure that I get valid, clickable URLs
 (7) "feedparser" in order to extract data from news feeds
 (8) "pandas"in order to manipulate CSV and tabular data
 (9) "Beautifulsoup" for web scraping
"""
import requests
import random
import time
import re
from collections import Counter
from urllib.parse import urljoin
import feedparser
import pandas as pd
from bs4 import BeautifulSoup

""" Load & filter FLELex (B2‑C2, rare, length > 6)
FLELex  is a research dataset that categorizes French words by  levels (A1, A2, B1, B2, C1, C2)
I'm interested only in advanced words that appear at C2 level.   
In order to focus on advanced words, additional restraints limit words of high frequency (less than 100) 
and short words (words with more than 6 characters)
Because the dataset is tab (not comma) separated, I use "sep="\t" 
Because of French accents, I use encoding="utf‑8"
Panda is used to read the French csv file into a table (dataframe)
The "str.strip" removes leading/trailing whitespace from all column names.
"""
flelex_path = "data/FLELex_TreeTagger.csv"
df = pd.read_csv(flelex_path, sep="\t", encoding="utf‑8")
df.columns = df.columns.str.strip()

rare_mask = (
    (df["freq_C2"] > 0)
) & (df["freq_total"] < 100) & (df["word"].str.len() > 6)

"""
This is a key variable that filters the words list to match the criteria for advanced words
Each row is being evaluated by rare_mask to produce a True or False value
This variable, "advanced_lemmas", is set a string.  Not sure if that's necessary, but just in case
df.loc lets me access the columns by labels--in this case, "words" 
I am using a "set" for faster lookup, since the program already runs a bit slow
"""
advanced_lemmas: set[str] = set(df.loc[rare_mask, "word"].str.lower())

"""
The next part cleans up Wiki formatting, removing bold/italic markers, stripping white spaces,
reducing multiple spaces, etc. 
"""

def _clean_wikicode(text: str) -> str:
    text = re.sub(r"\{\{[^}]*}}", "", text)
    text = re.sub(r"\[\[[^\]|]+\|([^]]+)]]", r"\1", text)
    text = re.sub(r"\[\[([^]]+)]]", r"\1", text)
    text = re.sub(r"''+", "", text)
    return re.sub(r"\s+", " ", text).strip()


#This next part provides French-language definitions of the words that match the above-defined "advanced"
#criteria. There are several sources provided in case of initial failure. (currently, dictionaryapi is
#not working for me).
#It uses an HTTP get request, with a time limit of five seconds to avoid hanging
#A status code of "200" means that the API response is OK
#The "meanings" line converts a JSON response to a Python object.  It gets the first entry (a dictionary)
# and then extracts its "meanings" list.
#A "for" loop is then used to This loop is looking through all parts of speech (meanings)
#and pulling the first actual definition it can find and then returning it
#The "if" statement makes sure that there’s at least one definition and that it’s not "None."
#The "return" line provides the first definition found, with leading/trailing spaces removed.
#The "pass" line  skips any error

def fetch_definition(word: str) -> str:
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/fr/{word}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            meanings = r.json()[0].get("meanings", [])
            for m in meanings:
                defs = m.get("definitions", [])
                if defs and defs[0].get("definition"):
                    return defs[0]["definition"].strip()
    except Exception:
        pass


#This is another source of definitions since dictionaryapi is causing problems.
#I exclude "etymologie" in order to focus on definitions, but this isn't working completely correctly
#The ?action=raw returns the wiki markup (not the formatted HTML page).
#Wiktionary uses # for definition lines
# ##  might be subpoints or examples
#The line "if clean" skips empty lines.
#The "clean = " line keeps only the first phrase of the definition (up to the first period or semicolon).
#I may reconsider this because some of the definitions are too short

    try:
        wurl = f"https://fr.wiktionary.org/wiki/{word}?action=raw&lang=fr"
        w = requests.get(wurl, timeout=5)
        if w.status_code == 200:
            for line in w.text.splitlines():
                line = line.strip()
                if line.startswith('#') and not line.startswith('##') and not 'étymologie' in line.lower():
                    clean = _clean_wikicode(line.lstrip('#'))
                    if clean:
                        clean = re.split(r"[.;]", clean)[0].strip()
                        return clean
    except Exception:
        pass


# Another fallback source of definitions.  May delete because Wiki seems adequate

    try:
        tatoeba_url = f"https://tatoeba.org/en/api_v0/search?from=fra&query={word}"
        r = requests.get(tatoeba_url, timeout=5)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return results[0].get("text", "").strip()
    except Exception:
        pass

    return lexicon_defs.get(word.lower(), "")


#This defines a class to fetch and process RSS-based news articles.
#the "self.rss_feeds" is a list of URLs for RSS feeds


class RSSScraper:
    def __init__(self) -> None:
        self.rss_feeds = [
            "https://www.france24.com/fr/rss",
            "https://www.lemonde.fr/rss/une.xml",
            "https://www.francetvinfo.fr/titres.rss",
            "https://www.radiofrance.fr/rss/arts-et-culture",
            "https://www.courrierinternational.com/feed/all/rss.xml",
            "https://www.rfi.fr/fr/rss",
            "https://www.sciencesetavenir.fr/rss.xml"
        ]
        self.article_sentences: list[str] = []


#This function loops through all RSS feeds, extracts summaries or descriptions from each article,
#and stop once it has collected 10 articles (defined in "max_articles")
#The "for" loop goes through all RSS feed URLs defined in self.rss_feeds
#The feedparser library to read the RSS feed


    def fetch_articles_from_rss(self, max_articles=10) -> list[str]:
        articles = []
        for feed in self.rss_feeds:
            try:
                parsed = feedparser.parse(feed)
                for entry in parsed.entries:
                    if 'summary' in entry:
                        articles.append(entry.summary)
                    elif 'description' in entry:
                        articles.append(entry.description)
                    if len(articles) >= max_articles:
                        return articles
            except Exception as e:
                print(f"RSS fetch error: {e}")
        return articles


#This next function filters words that, even though they meet the "advanced" requirements
#detailed above, are common words that shouldn't be included in the advanced list.
#Spacy has a library of "stop" words.
#I downloaded another list of thousands of French stop words from Github, which is saved
#in the "frequent_french_words_cleaned.txt" file

    def clean_and_count_words(self, text: str):
        try:
            import spacy
            nlp = spacy.load("fr_core_news_sm")
        except Exception:
            print("spaCy unavailable → skipping this article")
            return []

        try:
            with open("data/frequent_french_words.txt", encoding="utf-8") as f:
                common_words = set(w.strip().lower() for w in f if w.strip())
        except Exception:
            common_words = set()

# I added this exclusion list because easy, common words were slipping through the filters

        static_excluded = {
            "français", "française", "francais", "américain", "américaine", "americain",
            "france", "états-unis", "etats-unis", "europe", "paris", "washington",
            "macron", "trump", "biden", "netanyahu", "israël", "israel", "palestine",
            "gaza", "ukraine", "russie", "russia", "poutine", "zelensky", "onu",
            "pays", "ville", "territoire", "gouvernement", "président", "présidente",
            "avoir", "être", "faire", "mettre", "dire", "aller", "voir", "donner",
            "bon", "mauvais", "beau", "grand", "petit", "important", "nouveau",
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre",
            "donc", "mais", "ou", "et", "car", "cependant", "pourtant", "toutefois",
            "ainsi", "alors", "puis", "ensuite", "également"
        }

# This line creates a combined set of all the words to filter out

        excluded_words = static_excluded.union(common_words)


#The purpose of the next lines is to urns the text through the spaCy French language model (fr_core_news_sm).
        # tok.lemma_: the base form of the word (e.g., “marchait” → “marcher”)
        # .lower(): makes it lowercase for consistency
        # tok.pos_: the part of speech (like "NOUN", "VERB", etc.)
        # tok.is_alpha: Only keep words made of letters
        # len(tok) > 6 : Only keep long words (7 characters or more)
        #  tok.lemma_.lower() in advanced_lemmas : Only keep words in your filtered FLELex list (C2-level, low frequency)
        # tok.pos_ in {"NOUN", "VERB", "ADJ", "ADV"} :Excludes pronouns, prepositions, etc.
        # tok.lemma_.lower() not in excluded_words : Skip any words in the custom and frequency-based stopword lists



        doc = nlp(text)
        return [
            (tok.lemma_.lower(), tok.pos_)
            for tok in doc
            if (
                tok.is_alpha
                and len(tok) > 6
                and tok.lemma_.lower() in advanced_lemmas
                and tok.pos_ in {"NOUN", "VERB", "ADJ", "ADV"}
                and tok.lemma_.lower() not in excluded_words
            )
        ]

# The next function finds examples of word usage.
    # It looks through the list of article sentences (self.article_sentences), which was populated earlier from RSS text.
    # It then checks whether the target word appears in the lowercased version of the sentence.
    # If it finds one, it returns that sentence (with leading/trailing spaces removed using .strip()).
    # Otherwise, it falls back to Wiktionary or a generic example sentence

    def find_example_sentence(self, word: str) -> str:
        for s in self.article_sentences:
            if word in s.lower():
                return s.strip()
        try:
            wurl = (
                "https://fr.wiktionary.org/w/api.php?action=query&titles="
                f"{word}&prop=extracts&exsentences=1&explaintext=1&format=json"
            )
            r = requests.get(wurl, timeout=5)
            if r.status_code == 200:
                pages = r.json().get("query", {}).get("pages", {})
                for p in pages.values():
                    ext = p.get("extract", "").split(".")[0]
                    if ext:
                        return ext + "."
        except Exception:
            pass
        return f"Exemple par défaut : '{word}' est un mot avancé à connaître."


# This function puts everything together and provides output that can inputted into Anki as flashcards.

    def run(self, max_articles: int = 10):
        articles = self.fetch_articles_from_rss(max_articles)
        if not articles:
            print("No articles fetched.")
            return

        all_words = []

    # This for loop goes over the previously returned list of articles
        # It splits the article text into individual sentences using regular expressions
        # Then, it adds these sentences to the self.article_sentences list
        # This is later used to find example sentences for the vocab words

        for i, txt in enumerate(articles, 1):
            print(f"Processing article {i}/{len(articles)}")
            self.article_sentences.extend(re.split(r"[.!?]\s+", txt))
            all_words.extend(self.clean_and_count_words(txt))
            time.sleep(1)

        print(f"Total candidate tokens: {len(all_words)}")
        if not all_words:
            print("Nothing to process.")
            return

        counts = Counter(all_words)
        uniques = [(w, p) for (w, p), c in counts.items() if c == 1]
        sample = sorted(random.sample(uniques, min(30, len(uniques))), key=lambda x: x[0])

        flashcards: list[tuple[str, str, str, str]] = []
        print("\n" + "=" * 60)
        print("30 RARE, LONG ADVANCED WORDS WITH POS, DEFINITIONS & SENTENCES")
        print("=" * 60)
        for word, pos in sample:
            definition = fetch_definition(word) or "(définition indisponible)"
            sentence = self.find_example_sentence(word)
            english = ""
            if definition and definition != "(définition indisponible)":
                try:
                    tr = requests.post(
                        "https://libretranslate.com/translate",
                        data={"q": definition, "source": "fr", "target": "en"},
                        timeout=5,
                    ).json()
                    english = tr.get("translatedText", "")
                except Exception:
                    pass

            print(f"{word:20} ({pos})\n    Definition: {definition}\n    Example: {sentence}\n")
            flashcards.append((word, definition, sentence, english))

        with open("data/advanced_flashcard_words.tsv", "w", encoding="utf-8") as f:
            f.write("Word\tDefinition\tExample\tEnglish\n")
            for word, definition, sentence, english in flashcards:
                f.write(f"{word}\t{definition}\t{sentence}\t{english}\n")

if __name__ == "__main__":
    RSSScraper().run(max_articles=10)

"""
TrustCheck Name Normalizer.

Normalizes names for consistent matching across different formats and scripts.
"""

import re
import unicodedata

from unidecode import unidecode

# Common titles to remove
TITLES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "prof",
    "professor",
    "sir",
    "dame",
    "lord",
    "lady",
    "hon",
    "honorable",
    "rev",
    "reverend",
    "gen",
    "general",
    "col",
    "colonel",
    "maj",
    "major",
    "capt",
    "captain",
    "lt",
    "lieutenant",
    "sgt",
    "sergeant",
    "cpl",
    "corporal",
    "pvt",
    "private",
    "adm",
    "admiral",
    "sheikh",
    "shaikh",
    "ayatollah",
    "imam",
    "mullah",
    "haji",
    "hajj",
    "sayyid",
    "syed",
}

# Common suffixes to remove
SUFFIXES = {
    "jr",
    "junior",
    "sr",
    "senior",
    "ii",
    "iii",
    "iv",
    "v",
    "esq",
    "esquire",
    "phd",
    "md",
    "dds",
    "dvm",
    "jd",
    "llb",
    "llm",
    "mba",
    "cpa",
    "pe",
    "rn",
}

# Common organization suffixes
ORG_SUFFIXES = {
    "ltd",
    "limited",
    "llc",
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "plc",
    "gmbh",
    "ag",
    "sa",
    "srl",
    "bv",
    "nv",
    "ab",
    "as",
    "oy",
    "pty",
    "pvt",
    "pte",
}

# Character replacements for normalization
CHAR_REPLACEMENTS = {
    "ß": "ss",
    "æ": "ae",
    "œ": "oe",
    "ø": "o",
    "ł": "l",
    "đ": "d",
    "ð": "d",
    "þ": "th",
    "ñ": "n",
}


def normalize_name(name: str, remove_titles: bool = True, remove_suffixes: bool = True) -> str:
    """
    Normalize a name for matching.

    Steps:
    1. Convert to lowercase
    2. Transliterate unicode to ASCII
    3. Remove diacritics
    4. Remove titles (optional)
    5. Remove suffixes (optional)
    6. Remove punctuation
    7. Normalize whitespace
    8. Convert to uppercase

    Args:
        name: The name to normalize
        remove_titles: Whether to remove titles like Mr., Dr., etc.
        remove_suffixes: Whether to remove suffixes like Jr., III, etc.

    Returns:
        Normalized name string
    """
    if not name:
        return ""

    # Convert to lowercase for processing
    result = name.lower().strip()

    # Apply character replacements
    for old, new in CHAR_REPLACEMENTS.items():
        result = result.replace(old, new)

    # Transliterate unicode to ASCII (handles Cyrillic, Arabic, CJK, etc.)
    result = unidecode(result)

    # Remove diacritics that unidecode might have missed
    result = remove_diacritics(result)

    # Remove titles
    if remove_titles:
        result = remove_title_words(result)

    # Remove suffixes
    if remove_suffixes:
        result = remove_suffix_words(result)

    # Remove punctuation (keep spaces and alphanumeric)
    result = re.sub(r"[^\w\s]", " ", result)

    # Normalize whitespace
    result = " ".join(result.split())

    # Convert to uppercase for final result
    return result.upper()


def remove_diacritics(text: str) -> str:
    """Remove diacritical marks from text."""
    # Normalize to NFD (decomposed form)
    normalized = unicodedata.normalize("NFD", text)
    # Remove combining characters (diacritics)
    without_diacritics = "".join(c for c in normalized if not unicodedata.combining(c))
    # Normalize back to NFC
    return unicodedata.normalize("NFC", without_diacritics)


def remove_title_words(text: str) -> str:
    """Remove title words from text."""
    words = text.split()
    filtered = []

    for i, word in enumerate(words):
        # Clean word of punctuation for matching
        clean_word = re.sub(r"[^\w]", "", word).lower()
        # Only remove if it's at the start and is a known title
        if i == 0 and clean_word in TITLES:
            continue
        # Also check for title with period (e.g., "dr.")
        if clean_word.rstrip(".") in TITLES:
            continue
        filtered.append(word)

    return " ".join(filtered)


def remove_suffix_words(text: str) -> str:
    """Remove suffix words from text."""
    words = text.split()
    filtered = []

    for word in words:
        # Clean word of punctuation for matching
        clean_word = re.sub(r"[^\w]", "", word).lower()
        if clean_word in SUFFIXES or clean_word in ORG_SUFFIXES:
            continue
        filtered.append(word)

    return " ".join(filtered)


def tokenize_name(name: str) -> list[str]:
    """Split a name into tokens."""
    normalized = normalize_name(name)
    return normalized.split()


def generate_ngrams(text: str, n: int = 3) -> set[str]:
    """Generate character n-grams from text."""
    text = normalize_name(text).replace(" ", "")
    if len(text) < n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def detect_script(text: str) -> str:
    """Detect the primary script of a text."""
    if not text:
        return "LATIN"

    scripts = {
        "LATIN": 0,
        "CYRILLIC": 0,
        "ARABIC": 0,
        "CJK": 0,
        "HEBREW": 0,
        "GREEK": 0,
        "OTHER": 0,
    }

    for char in text:
        if char.isspace() or char.isdigit():
            continue

        name = unicodedata.name(char, "")

        if "LATIN" in name:
            scripts["LATIN"] += 1
        elif "CYRILLIC" in name:
            scripts["CYRILLIC"] += 1
        elif "ARABIC" in name:
            scripts["ARABIC"] += 1
        elif "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name or "HANGUL" in name:
            scripts["CJK"] += 1
        elif "HEBREW" in name:
            scripts["HEBREW"] += 1
        elif "GREEK" in name:
            scripts["GREEK"] += 1
        else:
            scripts["OTHER"] += 1

    # Return the most common script
    return max(scripts, key=scripts.get)  # type: ignore


def is_organization_name(name: str) -> bool:
    """Check if a name appears to be an organization name."""
    lower_name = name.lower()

    # Check for organization indicators
    org_indicators = [
        "company",
        "corporation",
        "incorporated",
        "limited",
        "llc",
        "ltd",
        "inc",
        "corp",
        "plc",
        "gmbh",
        "ag",
        "bank",
        "trading",
        "shipping",
        "airlines",
        "airways",
        "oil",
        "gas",
        "petroleum",
        "enterprise",
        "group",
        "holdings",
        "international",
        "foundation",
        "institute",
        "association",
        "organization",
        "ministry",
        "government",
        "agency",
        "authority",
        "committee",
        "council",
        "bureau",
        "department",
        "office",
    ]

    for indicator in org_indicators:
        if indicator in lower_name:
            return True

    # Check for all caps (often organizations)
    words = name.split()
    if len(words) >= 2 and all(w.isupper() for w in words if len(w) > 2):
        return True

    return False

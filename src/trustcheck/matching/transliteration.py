"""
TrustCheck Transliteration Module.

Advanced transliteration support for Arabic, Cyrillic, and other scripts.
Provides multiple transliteration variants for better matching.
"""

import re
from typing import Generator

# Arabic to Latin transliteration mappings (multiple variants per character)
ARABIC_TRANSLITERATION = {
    # Hamza
    "\u0621": ["'", ""],  # hamza
    "\u0623": ["a", "A", "'a"],  # alef with hamza above
    "\u0625": ["i", "e", "'i"],  # alef with hamza below
    "\u0624": ["u", "w", "'u"],  # waw with hamza above
    "\u0626": ["'", "y", "'y"],  # yeh with hamza above
    # Main letters
    "\u0627": ["a", "aa", ""],  # alef
    "\u0628": ["b"],  # beh
    "\u062a": ["t"],  # teh
    "\u062b": ["th", "s"],  # theh
    "\u062c": ["j", "g", "dj"],  # jeem (varies by dialect)
    "\u062d": ["h", "7"],  # hah
    "\u062e": ["kh", "5", "x"],  # khah
    "\u062f": ["d"],  # dal
    "\u0630": ["dh", "th", "z"],  # thal
    "\u0631": ["r"],  # reh
    "\u0632": ["z"],  # zain
    "\u0633": ["s"],  # seen
    "\u0634": ["sh", "ch"],  # sheen
    "\u0635": ["s", "9"],  # sad
    "\u0636": ["d", "dh"],  # dad
    "\u0637": ["t", "6"],  # tah
    "\u0638": ["z", "dh"],  # zah
    "\u0639": ["'", "a", "3"],  # ain
    "\u063a": ["gh", "8"],  # ghain
    "\u0641": ["f"],  # feh
    "\u0642": ["q", "k", "g"],  # qaf
    "\u0643": ["k"],  # kaf
    "\u0644": ["l"],  # lam
    "\u0645": ["m"],  # meem
    "\u0646": ["n"],  # noon
    "\u0647": ["h"],  # heh
    "\u0648": ["w", "u", "o", "oo"],  # waw
    "\u064a": ["y", "i", "ee"],  # yeh
    # Alef variations
    "\u0649": ["a", "y"],  # alef maksura
    "\u0671": ["a"],  # alef wasla
    # Teh marbuta
    "\u0629": ["a", "ah", "at", "h"],  # teh marbuta
    # Diacritics (usually ignored in names)
    "\u064b": [""],  # fathatan
    "\u064c": [""],  # dammatan
    "\u064d": [""],  # kasratan
    "\u064e": ["a"],  # fatha
    "\u064f": ["u"],  # damma
    "\u0650": ["i"],  # kasra
    "\u0651": [""],  # shadda (double letter indicator)
    "\u0652": [""],  # sukun
    # Common ligatures
    "\ufefb": ["la"],  # lam alef
    "\ufefc": ["la"],  # lam alef
}

# Cyrillic to Latin transliteration (GOST/BGN variants)
CYRILLIC_TRANSLITERATION = {
    # Russian
    "\u0410": ["a"],  # А
    "\u0411": ["b"],  # Б
    "\u0412": ["v", "w"],  # В
    "\u0413": ["g", "h"],  # Г
    "\u0414": ["d"],  # Д
    "\u0415": ["e", "ye"],  # Е
    "\u0416": ["zh", "j"],  # Ж
    "\u0417": ["z"],  # З
    "\u0418": ["i"],  # И
    "\u0419": ["y", "i", "j"],  # Й
    "\u041a": ["k"],  # К
    "\u041b": ["l"],  # Л
    "\u041c": ["m"],  # М
    "\u041d": ["n"],  # Н
    "\u041e": ["o"],  # О
    "\u041f": ["p"],  # П
    "\u0420": ["r"],  # Р
    "\u0421": ["s"],  # С
    "\u0422": ["t"],  # Т
    "\u0423": ["u", "ou"],  # У
    "\u0424": ["f", "ph"],  # Ф
    "\u0425": ["kh", "h", "x"],  # Х
    "\u0426": ["ts", "c"],  # Ц
    "\u0427": ["ch", "tch"],  # Ч
    "\u0428": ["sh"],  # Ш
    "\u0429": ["shch", "sch"],  # Щ
    "\u042a": ["", "'"],  # Ъ (hard sign)
    "\u042b": ["y", "i"],  # Ы
    "\u042c": ["", "'"],  # Ь (soft sign)
    "\u042d": ["e"],  # Э
    "\u042e": ["yu", "iu", "ju"],  # Ю
    "\u042f": ["ya", "ia", "ja"],  # Я
    # Ukrainian additions
    "\u0404": ["ye", "ie"],  # Є
    "\u0406": ["i"],  # І
    "\u0407": ["yi", "ji"],  # Ї
    "\u0490": ["g", "gh"],  # Ґ
    # Lowercase versions (same mappings)
    "\u0430": ["a"],
    "\u0431": ["b"],
    "\u0432": ["v", "w"],
    "\u0433": ["g", "h"],
    "\u0434": ["d"],
    "\u0435": ["e", "ye"],
    "\u0436": ["zh", "j"],
    "\u0437": ["z"],
    "\u0438": ["i"],
    "\u0439": ["y", "i", "j"],
    "\u043a": ["k"],
    "\u043b": ["l"],
    "\u043c": ["m"],
    "\u043d": ["n"],
    "\u043e": ["o"],
    "\u043f": ["p"],
    "\u0440": ["r"],
    "\u0441": ["s"],
    "\u0442": ["t"],
    "\u0443": ["u", "ou"],
    "\u0444": ["f", "ph"],
    "\u0445": ["kh", "h", "x"],
    "\u0446": ["ts", "c"],
    "\u0447": ["ch", "tch"],
    "\u0448": ["sh"],
    "\u0449": ["shch", "sch"],
    "\u044a": ["", "'"],
    "\u044b": ["y", "i"],
    "\u044c": ["", "'"],
    "\u044d": ["e"],
    "\u044e": ["yu", "iu", "ju"],
    "\u044f": ["ya", "ia", "ja"],
    "\u0454": ["ye", "ie"],
    "\u0456": ["i"],
    "\u0457": ["yi", "ji"],
    "\u0491": ["g", "gh"],
}


def transliterate_arabic(text: str) -> list[str]:
    """
    Transliterate Arabic text to Latin with multiple variants.

    Returns a list of possible transliterations.
    """
    if not text:
        return [""]

    # Check if text contains Arabic characters
    if not any("\u0600" <= c <= "\u06ff" for c in text):
        return [text]

    # Generate variants recursively
    variants = _generate_variants(text, ARABIC_TRANSLITERATION)

    # Clean up variants
    cleaned = set()
    for v in variants:
        v = re.sub(r"\s+", " ", v).strip()
        if v:
            cleaned.add(v)

    return list(cleaned)[:10]  # Limit to top 10 variants


def transliterate_cyrillic(text: str) -> list[str]:
    """
    Transliterate Cyrillic text to Latin with multiple variants.

    Returns a list of possible transliterations.
    """
    if not text:
        return [""]

    # Check if text contains Cyrillic characters
    if not any("\u0400" <= c <= "\u04ff" for c in text):
        return [text]

    # Generate variants
    variants = _generate_variants(text, CYRILLIC_TRANSLITERATION)

    # Clean up variants
    cleaned = set()
    for v in variants:
        v = re.sub(r"\s+", " ", v).strip()
        if v:
            cleaned.add(v)

    return list(cleaned)[:10]


def _generate_variants(text: str, mapping: dict[str, list[str]]) -> Generator[str, None, None]:
    """Generate transliteration variants recursively."""
    if not text:
        yield ""
        return

    char = text[0]
    rest = text[1:]

    # Get transliterations for this character
    if char in mapping:
        transliterations = mapping[char]
    else:
        transliterations = [char]

    # Recursively generate rest
    for rest_variant in _generate_variants(rest, mapping):
        for trans in transliterations:
            yield trans + rest_variant


def get_all_transliterations(text: str) -> list[str]:
    """
    Get all transliteration variants for a text.

    Handles Arabic, Cyrillic, and mixed scripts.
    """
    if not text:
        return [""]

    variants = set()
    variants.add(text)

    # Try Arabic transliteration
    arabic_variants = transliterate_arabic(text)
    variants.update(arabic_variants)

    # Try Cyrillic transliteration
    cyrillic_variants = transliterate_cyrillic(text)
    variants.update(cyrillic_variants)

    # Also try transliterating each word separately
    words = text.split()
    if len(words) > 1:
        # Generate variants per word
        word_variants: list[list[str]] = []
        for word in words:
            word_vars = set()
            word_vars.add(word)
            word_vars.update(transliterate_arabic(word))
            word_vars.update(transliterate_cyrillic(word))
            word_variants.append(list(word_vars)[:5])

        # Combine (limited to avoid explosion)
        from itertools import product
        for combo in list(product(*word_variants))[:20]:
            variants.add(" ".join(combo))

    return list(variants)[:20]


# Common Arabic name patterns and their Latin equivalents
ARABIC_NAME_PATTERNS = {
    # "Abdul" variations
    r"عبد\s*ال": "abd al-",
    r"عبدال": "abdul",
    # "Abu" variations
    r"أبو\s*": "abu ",
    r"ابو\s*": "abu ",
    # "bin/ibn" (son of)
    r"\s*بن\s*": " bin ",
    r"\s*ابن\s*": " ibn ",
    # "al-" (the)
    r"\s*ال(?=[ا-ي])": " al-",
}


def normalize_arabic_name(text: str) -> list[str]:
    """
    Normalize an Arabic name with common pattern recognition.

    Handles common prefixes like Abdul, Abu, bin/ibn, al-.
    """
    variants = []

    # Apply pattern replacements
    for pattern, replacement in ARABIC_NAME_PATTERNS.items():
        text = re.sub(pattern, replacement, text)

    # Get basic transliterations
    variants.extend(get_all_transliterations(text))

    return variants

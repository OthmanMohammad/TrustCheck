"""
TrustCheck Phonetic Matching.

Implements phonetic algorithms for matching names that sound similar
but may be spelled differently.
"""

import re
from functools import lru_cache

import jellyfish

from trustcheck.matching.normalizer import normalize_name, tokenize_name


def _sanitize_for_phonetic(text: str) -> str:
    """
    Sanitize text for phonetic algorithms.

    Removes non-alphabetical characters that can cause errors
    in phonetic encoding functions like match_rating_codex.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized text containing only alphabetical characters
    """
    if not text:
        return ""
    # Keep only alphabetical characters
    sanitized = re.sub(r'[^a-zA-Z]', '', text)
    return sanitized


@lru_cache(maxsize=10000)
def soundex(text: str) -> str:
    """
    Generate Soundex code for a string.

    Soundex is a phonetic algorithm that encodes words by sound,
    as pronounced in English. Useful for matching names that sound
    similar but are spelled differently.

    Args:
        text: The text to encode

    Returns:
        Soundex code (4 characters)
    """
    sanitized = _sanitize_for_phonetic(text)
    if not sanitized:
        return ""
    return jellyfish.soundex(sanitized)


@lru_cache(maxsize=10000)
def metaphone(text: str) -> str:
    """
    Generate Metaphone code for a string.

    Metaphone is a phonetic algorithm that encodes words by their
    English pronunciation. More accurate than Soundex for many names.

    Args:
        text: The text to encode

    Returns:
        Metaphone code
    """
    sanitized = _sanitize_for_phonetic(text)
    if not sanitized:
        return ""
    return jellyfish.metaphone(sanitized)


@lru_cache(maxsize=10000)
def nysiis(text: str) -> str:
    """
    Generate NYSIIS code for a string.

    NYSIIS (New York State Identification and Intelligence System)
    is a phonetic algorithm designed for encoding names.

    Args:
        text: The text to encode

    Returns:
        NYSIIS code
    """
    sanitized = _sanitize_for_phonetic(text)
    if not sanitized:
        return ""
    return jellyfish.nysiis(sanitized)


@lru_cache(maxsize=10000)
def match_rating_codex(text: str) -> str:
    """
    Generate Match Rating Approach codex for a string.

    The Match Rating Approach encodes a string for comparison using
    phonetic similarity.

    Args:
        text: The text to encode

    Returns:
        MRA codex
    """
    sanitized = _sanitize_for_phonetic(text)
    if not sanitized:
        return ""
    return jellyfish.match_rating_codex(sanitized)


def get_phonetic_codes(name: str) -> dict[str, list[str]]:
    """
    Generate all phonetic codes for a name.

    Tokenizes the name and generates phonetic codes for each token.

    Args:
        name: The name to encode

    Returns:
        Dictionary with algorithm names as keys and lists of codes as values
    """
    tokens = tokenize_name(name)

    return {
        "soundex": [soundex(t) for t in tokens if t],
        "metaphone": [metaphone(t) for t in tokens if t],
        "nysiis": [nysiis(t) for t in tokens if t],
        "mra": [match_rating_codex(t) for t in tokens if t],
    }


def phonetic_match(name1: str, name2: str) -> dict[str, bool]:
    """
    Check if two names match phonetically using various algorithms.

    Args:
        name1: First name
        name2: Second name

    Returns:
        Dictionary with algorithm names and whether they match
    """
    codes1 = get_phonetic_codes(name1)
    codes2 = get_phonetic_codes(name2)

    results = {}

    # Soundex match - all tokens must match
    results["soundex"] = _codes_match(codes1["soundex"], codes2["soundex"])

    # Metaphone match
    results["metaphone"] = _codes_match(codes1["metaphone"], codes2["metaphone"])

    # NYSIIS match
    results["nysiis"] = _codes_match(codes1["nysiis"], codes2["nysiis"])

    # MRA match
    results["mra"] = _codes_match(codes1["mra"], codes2["mra"])

    # Overall match - at least 2 algorithms agree
    results["any"] = sum(results.values()) >= 2

    return results


def _codes_match(codes1: list[str], codes2: list[str]) -> bool:
    """Check if two lists of codes match (order independent)."""
    if not codes1 or not codes2:
        return False

    # Sort both lists for comparison
    sorted1 = sorted(codes1)
    sorted2 = sorted(codes2)

    # Exact match
    if sorted1 == sorted2:
        return True

    # Partial match - at least 50% of codes match
    set1 = set(codes1)
    set2 = set(codes2)
    intersection = set1 & set2

    if not intersection:
        return False

    # At least half of the smaller set should match
    min_len = min(len(set1), len(set2))
    return len(intersection) >= min_len / 2


def phonetic_similarity_score(name1: str, name2: str) -> float:
    """
    Calculate a phonetic similarity score between two names.

    Args:
        name1: First name
        name2: Second name

    Returns:
        Similarity score from 0.0 to 1.0
    """
    matches = phonetic_match(name1, name2)

    # Weight the different algorithms
    weights = {
        "soundex": 0.20,
        "metaphone": 0.30,
        "nysiis": 0.30,
        "mra": 0.20,
    }

    score = sum(weights[algo] for algo, matched in matches.items() if matched and algo in weights)

    return min(1.0, score)


def get_primary_phonetic_key(name: str) -> str:
    """
    Get a primary phonetic key for indexing.

    Uses a combination of Metaphone codes for the name tokens,
    which provides a good balance of accuracy and simplicity.

    Args:
        name: The name to encode

    Returns:
        Phonetic key string
    """
    tokens = tokenize_name(name)
    if not tokens:
        return ""

    # Use metaphone codes joined by hyphen
    codes = [metaphone(t) for t in tokens if t]
    return "-".join(codes) if codes else ""

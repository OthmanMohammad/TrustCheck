"""
TrustCheck Matching Engine.

Name matching and scoring for sanctions screening.
Enhanced with transliteration and nickname/variant support.
"""

from trustcheck.matching.nicknames import (
    expand_name_with_variants,
    get_canonical_name,
    get_name_variants,
    names_are_variants,
)
from trustcheck.matching.normalizer import (
    detect_script,
    generate_ngrams,
    is_organization_name,
    normalize_name,
    tokenize_name,
)
from trustcheck.matching.phonetic import (
    get_phonetic_codes,
    get_primary_phonetic_key,
    metaphone,
    nysiis,
    phonetic_match,
    phonetic_similarity_score,
    soundex,
)
from trustcheck.matching.scorer import (
    MatchScore,
    NameMatcher,
    get_matcher,
    is_match,
    score_match,
)
from trustcheck.matching.transliteration import (
    get_all_transliterations,
    normalize_arabic_name,
    transliterate_arabic,
    transliterate_cyrillic,
)

__all__ = [
    # Normalizer
    "detect_script",
    "generate_ngrams",
    "is_organization_name",
    "normalize_name",
    "tokenize_name",
    # Phonetic
    "get_phonetic_codes",
    "get_primary_phonetic_key",
    "metaphone",
    "nysiis",
    "phonetic_match",
    "phonetic_similarity_score",
    "soundex",
    # Scorer
    "MatchScore",
    "NameMatcher",
    "get_matcher",
    "is_match",
    "score_match",
    # Transliteration
    "get_all_transliterations",
    "normalize_arabic_name",
    "transliterate_arabic",
    "transliterate_cyrillic",
    # Nicknames/Variants
    "expand_name_with_variants",
    "get_canonical_name",
    "get_name_variants",
    "names_are_variants",
]

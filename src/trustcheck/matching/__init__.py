"""
TrustCheck Matching Engine.

Name matching and scoring for sanctions screening.
"""

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
]

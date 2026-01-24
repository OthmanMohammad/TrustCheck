"""
TrustCheck Match Scorer.

Comprehensive name matching and scoring using multiple algorithms.
Enhanced with transliteration and nickname/variant matching.
"""

from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from trustcheck.domain.enums import MatchType
from trustcheck.matching.nicknames import expand_name_with_variants, names_are_variants
from trustcheck.matching.normalizer import generate_ngrams, normalize_name, tokenize_name
from trustcheck.matching.phonetic import phonetic_match, phonetic_similarity_score
from trustcheck.matching.transliteration import get_all_transliterations


@dataclass
class MatchScore:
    """Detailed match score breakdown."""

    overall_score: float
    match_type: MatchType
    exact_match: bool
    normalized_match: bool
    phonetic_match: bool

    # Individual algorithm scores (0-100)
    ratio_score: float
    partial_ratio_score: float
    token_sort_score: float
    token_set_score: float

    # Phonetic details
    phonetic_score: float
    phonetic_algorithms: dict[str, bool]

    # N-gram similarity
    ngram_score: float

    # Fields with defaults must come last
    variant_match: bool = False  # True if names are known variants (Bob/Robert)
    variant_bonus: float = 0.0


class NameMatcher:
    """
    High-performance name matching engine.

    Uses a combination of:
    - Exact matching
    - Normalized string matching
    - Fuzzy string matching (Levenshtein, Jaro-Winkler)
    - Phonetic matching (Soundex, Metaphone, NYSIIS)
    - N-gram similarity
    - Nickname/variant matching (Bob/Robert, Muhammad/Mohammed)
    - Transliteration matching (Arabic/Cyrillic to Latin)
    """

    def __init__(
        self,
        default_threshold: float = 0.80,
        weights: dict[str, float] | None = None,
        enable_variants: bool = True,
        enable_transliteration: bool = True,
    ) -> None:
        """
        Initialize the matcher.

        Args:
            default_threshold: Default minimum score for a match (0.0-1.0)
            weights: Custom weights for different algorithms
            enable_variants: Enable nickname/variant matching
            enable_transliteration: Enable transliteration for non-Latin scripts
        """
        self.default_threshold = default_threshold
        self.weights = weights or {
            "ratio": 0.15,
            "partial_ratio": 0.15,
            "token_sort": 0.25,
            "token_set": 0.25,
            "phonetic": 0.15,
            "ngram": 0.05,
        }
        self.enable_variants = enable_variants
        self.enable_transliteration = enable_transliteration
        self.variant_bonus = 0.15  # Bonus for known variant matches

    def score(self, query: str, candidate: str) -> MatchScore:
        """
        Calculate a comprehensive match score between two names.

        Args:
            query: The search query name
            candidate: The candidate name to match against

        Returns:
            MatchScore with detailed breakdown
        """
        # Normalize both names
        query_norm = normalize_name(query)
        candidate_norm = normalize_name(candidate)

        # Check for exact matches
        exact_match = query.strip().upper() == candidate.strip().upper()
        normalized_match = query_norm == candidate_norm

        # Check for variant match (Bob/Robert, Muhammad/Mohammed)
        variant_match = False
        variant_bonus = 0.0
        if self.enable_variants and not normalized_match:
            variant_match = names_are_variants(query, candidate)
            if variant_match:
                variant_bonus = self.variant_bonus

        # If exact or normalized match, return perfect score
        if exact_match:
            return MatchScore(
                overall_score=1.0,
                match_type=MatchType.EXACT,
                exact_match=True,
                normalized_match=True,
                phonetic_match=True,
                variant_match=variant_match,
                ratio_score=100.0,
                partial_ratio_score=100.0,
                token_sort_score=100.0,
                token_set_score=100.0,
                phonetic_score=1.0,
                phonetic_algorithms={"soundex": True, "metaphone": True, "nysiis": True, "mra": True},
                ngram_score=1.0,
                variant_bonus=0.0,
            )

        if normalized_match:
            return MatchScore(
                overall_score=0.99,
                match_type=MatchType.NORMALIZED,
                exact_match=False,
                normalized_match=True,
                phonetic_match=True,
                variant_match=variant_match,
                ratio_score=100.0,
                partial_ratio_score=100.0,
                token_sort_score=100.0,
                token_set_score=100.0,
                phonetic_score=1.0,
                phonetic_algorithms={"soundex": True, "metaphone": True, "nysiis": True, "mra": True},
                ngram_score=1.0,
                variant_bonus=0.0,
            )

        # Try transliteration if enabled and names contain non-Latin
        best_ratio_score = 0.0
        best_token_sort_score = 0.0

        if self.enable_transliteration:
            query_variants = get_all_transliterations(query)
            candidate_variants = get_all_transliterations(candidate)

            # Find best score among transliteration variants
            for qv in query_variants[:5]:
                qv_norm = normalize_name(qv)
                for cv in candidate_variants[:5]:
                    cv_norm = normalize_name(cv)
                    r = fuzz.ratio(qv_norm, cv_norm)
                    ts = fuzz.token_sort_ratio(qv_norm, cv_norm)
                    if r > best_ratio_score:
                        best_ratio_score = r
                    if ts > best_token_sort_score:
                        best_token_sort_score = ts

        # Calculate fuzzy scores (rapidfuzz returns 0-100)
        ratio_score = max(fuzz.ratio(query_norm, candidate_norm), best_ratio_score)
        partial_ratio_score = fuzz.partial_ratio(query_norm, candidate_norm)
        token_sort_score = max(fuzz.token_sort_ratio(query_norm, candidate_norm), best_token_sort_score)
        token_set_score = fuzz.token_set_ratio(query_norm, candidate_norm)

        # Calculate phonetic match
        phonetic_algorithms = phonetic_match(query, candidate)
        is_phonetic_match = phonetic_algorithms.get("any", False)
        phonetic_score = phonetic_similarity_score(query, candidate)

        # Calculate n-gram similarity
        ngram_score = self._ngram_similarity(query_norm, candidate_norm)

        # Calculate weighted overall score
        overall_score = (
            self.weights["ratio"] * (ratio_score / 100)
            + self.weights["partial_ratio"] * (partial_ratio_score / 100)
            + self.weights["token_sort"] * (token_sort_score / 100)
            + self.weights["token_set"] * (token_set_score / 100)
            + self.weights["phonetic"] * phonetic_score
            + self.weights["ngram"] * ngram_score
        )

        # Apply variant bonus
        if variant_match:
            overall_score = min(1.0, overall_score + variant_bonus)

        # Determine match type
        if variant_match and overall_score >= 0.70:
            match_type = MatchType.VARIANT if hasattr(MatchType, 'VARIANT') else MatchType.FUZZY
        elif is_phonetic_match and overall_score >= 0.70:
            match_type = MatchType.PHONETIC
        elif token_set_score >= 80 and overall_score >= 0.60:
            match_type = MatchType.FUZZY
        elif partial_ratio_score >= 90:
            match_type = MatchType.PARTIAL
        else:
            match_type = MatchType.FUZZY

        return MatchScore(
            overall_score=round(overall_score, 4),
            match_type=match_type,
            exact_match=exact_match,
            normalized_match=normalized_match,
            phonetic_match=is_phonetic_match,
            variant_match=variant_match,
            ratio_score=ratio_score,
            partial_ratio_score=partial_ratio_score,
            token_sort_score=token_sort_score,
            token_set_score=token_set_score,
            phonetic_score=phonetic_score,
            phonetic_algorithms=phonetic_algorithms,
            ngram_score=ngram_score,
            variant_bonus=variant_bonus,
        )

    def is_match(self, query: str, candidate: str, threshold: float | None = None) -> bool:
        """
        Check if two names match above the threshold.

        Args:
            query: The search query name
            candidate: The candidate name to match against
            threshold: Minimum score for a match (uses default if not specified)

        Returns:
            True if the names match above threshold
        """
        threshold = threshold or self.default_threshold
        score = self.score(query, candidate)
        return score.overall_score >= threshold

    def find_matches(
        self,
        query: str,
        candidates: list[tuple[str, str, str]],  # (entity_id, normalized_name, original_name)
        threshold: float | None = None,
        max_results: int = 100,
    ) -> list[tuple[str, str, MatchScore]]:
        """
        Find all matching candidates for a query.

        Args:
            query: The search query name
            candidates: List of (entity_id, normalized_name, original_name) tuples
            threshold: Minimum score for a match
            max_results: Maximum number of results to return

        Returns:
            List of (entity_id, original_name, MatchScore) tuples, sorted by score
        """
        threshold = threshold or self.default_threshold
        matches = []

        query_norm = normalize_name(query)

        # Get query variants for expanded matching
        query_variants = set()
        if self.enable_variants:
            query_variants = expand_name_with_variants(query)

        for entity_id, normalized_name, original_name in candidates:
            # Quick pre-filter using normalized comparison
            if self._quick_filter(query_norm, normalized_name, query_variants):
                score = self.score(query, original_name)
                if score.overall_score >= threshold:
                    matches.append((entity_id, original_name, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[2].overall_score, reverse=True)

        return matches[:max_results]

    def _quick_filter(
        self,
        query_norm: str,
        candidate_norm: str,
        query_variants: set[str] | None = None,
    ) -> bool:
        """
        Quick pre-filter to eliminate obvious non-matches.

        Uses simple heuristics to avoid expensive scoring for clearly different names.
        """
        # Length check - if lengths differ by more than 50%, probably not a match
        len_ratio = len(query_norm) / max(len(candidate_norm), 1)
        if len_ratio < 0.5 or len_ratio > 2.0:
            return False

        # Check if they share at least one token
        query_tokens = set(query_norm.split())
        candidate_tokens = set(candidate_norm.split())

        if not query_tokens or not candidate_tokens:
            return True

        # If they share any tokens, keep for detailed scoring
        if query_tokens & candidate_tokens:
            return True

        # Check if any variant tokens match
        if query_variants:
            variant_tokens = set()
            for v in query_variants:
                variant_tokens.update(normalize_name(v).split())
            if variant_tokens & candidate_tokens:
                return True

        # Check first character of first token
        if query_norm and candidate_norm:
            if query_norm[0] == candidate_norm[0]:
                return True

        # Check n-gram overlap (quick version)
        query_ngrams = generate_ngrams(query_norm, 2)
        candidate_ngrams = generate_ngrams(candidate_norm, 2)

        if query_ngrams and candidate_ngrams:
            overlap = len(query_ngrams & candidate_ngrams) / min(len(query_ngrams), len(candidate_ngrams))
            if overlap >= 0.2:
                return True

        return False

    def _ngram_similarity(self, text1: str, text2: str, n: int = 3) -> float:
        """Calculate n-gram (Jaccard) similarity between two texts."""
        ngrams1 = generate_ngrams(text1, n)
        ngrams2 = generate_ngrams(text2, n)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        return intersection / union if union > 0 else 0.0


# Global matcher instance
_matcher: NameMatcher | None = None


def get_matcher() -> NameMatcher:
    """Get the global matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = NameMatcher()
    return _matcher


def score_match(query: str, candidate: str) -> MatchScore:
    """Score a match using the global matcher."""
    return get_matcher().score(query, candidate)


def is_match(query: str, candidate: str, threshold: float = 0.80) -> bool:
    """Check if two names match using the global matcher."""
    return get_matcher().is_match(query, candidate, threshold)

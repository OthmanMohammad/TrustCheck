"""
TrustCheck Matching Engine Tests.

Unit tests for the name matching algorithms.
"""

import pytest

from trustcheck.matching import (
    MatchScore,
    NameMatcher,
    detect_script,
    generate_ngrams,
    is_match,
    is_organization_name,
    metaphone,
    normalize_name,
    phonetic_match,
    phonetic_similarity_score,
    score_match,
    soundex,
    tokenize_name,
)


class TestNormalization:
    """Tests for name normalization."""

    def test_basic_normalization(self):
        """Test basic name normalization."""
        assert normalize_name("John Smith") == "JOHN SMITH"
        assert normalize_name("  john   smith  ") == "JOHN SMITH"

    def test_unicode_transliteration(self):
        """Test Unicode transliteration."""
        # Cyrillic
        assert "VLADIMIR" in normalize_name("Владимир")
        # German eszett
        assert "SS" in normalize_name("Strauß")
        # Diacritics
        assert normalize_name("José García") == "JOSE GARCIA"

    def test_title_removal(self):
        """Test removal of titles."""
        assert normalize_name("Dr. John Smith") == "JOHN SMITH"
        assert normalize_name("Mr. James Bond") == "JAMES BOND"
        assert normalize_name("Prof. Albert Einstein") == "ALBERT EINSTEIN"

    def test_suffix_removal(self):
        """Test removal of suffixes."""
        assert normalize_name("John Smith Jr.") == "JOHN SMITH"
        assert normalize_name("Robert Johnson III") == "ROBERT JOHNSON"
        assert normalize_name("Jane Doe, PhD") == "JANE DOE"

    def test_punctuation_removal(self):
        """Test punctuation handling."""
        assert normalize_name("John-Smith") == "JOHN SMITH"
        assert normalize_name("O'Brien") == "O BRIEN"  # Apostrophe becomes space
        assert normalize_name("Smith, John") == "SMITH JOHN"

    def test_empty_and_none(self):
        """Test edge cases."""
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""


class TestTokenization:
    """Tests for name tokenization."""

    def test_tokenize(self):
        """Test name tokenization."""
        tokens = tokenize_name("John Doe Smith")
        assert tokens == ["JOHN", "DOE", "SMITH"]

    def test_tokenize_with_titles(self):
        """Test tokenization removes titles."""
        tokens = tokenize_name("Dr. John Smith")
        assert "DR" not in tokens


class TestNgrams:
    """Tests for n-gram generation."""

    def test_trigrams(self):
        """Test trigram generation."""
        ngrams = generate_ngrams("JOHN", 3)
        assert "JOH" in ngrams
        assert "OHN" in ngrams

    def test_short_text(self):
        """Test n-grams for short text."""
        # For text shorter than n, use bigrams instead
        ngrams = generate_ngrams("ABC", 3)
        assert "ABC" in ngrams
        # Text exactly length n
        ngrams = generate_ngrams("ABCD", 3)
        assert "ABC" in ngrams
        assert "BCD" in ngrams


class TestScriptDetection:
    """Tests for script detection."""

    def test_latin(self):
        """Test Latin script detection."""
        assert detect_script("John Smith") == "LATIN"

    def test_cyrillic(self):
        """Test Cyrillic script detection."""
        assert detect_script("Владимир Путин") == "CYRILLIC"

    def test_arabic(self):
        """Test Arabic script detection."""
        assert detect_script("محمد علي") == "ARABIC"


class TestOrganizationDetection:
    """Tests for organization name detection."""

    def test_organization_indicators(self):
        """Test organization detection."""
        assert is_organization_name("ABC Corporation")
        assert is_organization_name("XYZ Limited")
        assert is_organization_name("Test Company LLC")
        assert is_organization_name("First National Bank")

    def test_individual_names(self):
        """Test that individual names are not flagged."""
        assert not is_organization_name("John Smith")
        assert not is_organization_name("Mohammad Ali Khan")


class TestPhonetic:
    """Tests for phonetic algorithms."""

    def test_soundex(self):
        """Test Soundex encoding."""
        # Same Soundex for similar sounding names
        assert soundex("Robert") == soundex("Rupert")
        assert soundex("Smith") == soundex("Smythe")

    def test_metaphone(self):
        """Test Metaphone encoding."""
        # Similar sounding names should have same code
        m1 = metaphone("Mohammad")
        m2 = metaphone("Mohammed")
        assert m1 == m2

    def test_phonetic_match(self):
        """Test phonetic matching."""
        result = phonetic_match("Mohammad Ali", "Mohammed Ali")
        assert result["any"] is True

    def test_phonetic_similarity(self):
        """Test phonetic similarity score."""
        score = phonetic_similarity_score("John", "Jon")
        assert score > 0.5


class TestScorer:
    """Tests for the name matching scorer."""

    def test_exact_match(self):
        """Test exact name matching."""
        score = score_match("John Smith", "John Smith")
        assert score.overall_score == 1.0
        assert score.exact_match is True

    def test_normalized_match(self):
        """Test normalized matching."""
        score = score_match("john smith", "JOHN SMITH")
        assert score.overall_score >= 0.99
        assert score.normalized_match is True

    def test_fuzzy_match(self):
        """Test fuzzy matching."""
        score = score_match("Jon Smith", "John Smith")
        assert score.overall_score > 0.8

    def test_phonetic_match(self):
        """Test phonetic matching."""
        score = score_match("Mohammad Ali Khan", "Mohammed Ali Khan")
        assert score.overall_score > 0.85
        assert score.phonetic_match is True

    def test_partial_match(self):
        """Test partial name matching."""
        score = score_match("John", "John Smith")
        assert score.overall_score > 0.5

    def test_no_match(self):
        """Test non-matching names."""
        score = score_match("John Smith", "Jane Doe")
        assert score.overall_score < 0.5


class TestNameMatcher:
    """Tests for the NameMatcher class."""

    def test_is_match(self):
        """Test is_match method."""
        matcher = NameMatcher(default_threshold=0.8)

        assert matcher.is_match("John Smith", "John Smith")
        assert matcher.is_match("Mohammad Ali", "Mohammed Ali")
        assert not matcher.is_match("John Smith", "Jane Doe")

    def test_is_match_with_threshold(self):
        """Test is_match with custom threshold."""
        assert is_match("Jon Smith", "John Smith", threshold=0.7)
        assert not is_match("Jon Smith", "John Smith", threshold=0.99)

    def test_find_matches(self):
        """Test finding matches from a list."""
        matcher = NameMatcher()

        candidates = [
            ("1", "JOHN SMITH", "John Smith"),
            ("2", "JANE DOE", "Jane Doe"),
            ("3", "JON SMITH", "Jon Smith"),
            ("4", "MOHAMMED ALI", "Mohammed Ali"),
        ]

        matches = matcher.find_matches("John Smith", candidates, threshold=0.7)

        # Should find John Smith and Jon Smith
        assert len(matches) >= 1
        assert matches[0][0] == "1"  # Exact match first

    def test_find_matches_phonetic(self):
        """Test finding phonetic matches."""
        matcher = NameMatcher()

        candidates = [
            ("1", "MOHAMMAD ALI KHAN", "Mohammad Ali Khan"),
            ("2", "JOHN DOE", "John Doe"),
        ]

        matches = matcher.find_matches("Mohammed Ali Khan", candidates, threshold=0.8)
        assert len(matches) >= 1
        assert matches[0][0] == "1"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_strings(self):
        """Test handling of empty strings."""
        assert normalize_name("") == ""
        score = score_match("", "")
        assert score.overall_score >= 0

    def test_single_character(self):
        """Test single character names."""
        assert normalize_name("A") == "A"
        score = score_match("A", "A")
        assert score.overall_score == 1.0

    def test_very_long_names(self):
        """Test very long names."""
        long_name = "A" * 500
        normalized = normalize_name(long_name)
        assert len(normalized) == 500

    def test_special_characters(self):
        """Test names with special characters."""
        assert normalize_name("José María García-López") == "JOSE MARIA GARCIA LOPEZ"

"""Tests for admin security validation logic."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.api.admin_validators import (  # noqa: E402
    MAX_LANGUAGES_COUNT,
    MAX_MEDIA_URLS_COUNT,
    MAX_URL_LENGTH,
    _validate_currency,
    _validate_language_code,
    _validate_languages,
    _validate_logo_media_url,
    _validate_media_urls,
    _validate_string_length,
    _validate_url,
)
from app.exceptions import ValidationError  # noqa: E402


class TestValidateStringLength:
    """Tests for string length validation."""

    def test_valid_string(self) -> None:
        """Valid string should pass validation."""
        result = _validate_string_length("Test Name", "name", 200)
        assert result == "Test Name"

    def test_string_stripped(self) -> None:
        """Whitespace should be stripped."""
        result = _validate_string_length("  Test Name  ", "name", 200)
        assert result == "Test Name"

    def test_none_value_optional(self) -> None:
        """None value should return None when not required."""
        result = _validate_string_length(None, "name", 200, required=False)
        assert result is None

    def test_none_value_required(self) -> None:
        """None value should raise error when required."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_string_length(None, "name", 200, required=True)
        assert "name is required" in str(exc_info.value)

    def test_empty_string_required(self) -> None:
        """Empty string should raise error when required."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_string_length("", "name", 200, required=True)
        assert "name is required" in str(exc_info.value)

    def test_whitespace_only_required(self) -> None:
        """Whitespace-only string should raise error when required."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_string_length("   ", "name", 200, required=True)
        assert "name is required" in str(exc_info.value)

    def test_string_too_long(self) -> None:
        """String exceeding max length should raise error."""
        long_string = "a" * 201
        with pytest.raises(ValidationError) as exc_info:
            _validate_string_length(long_string, "name", 200)
        assert "must be at most 200 characters" in str(exc_info.value)

    def test_boundary_length(self) -> None:
        """String at exactly max length should pass."""
        exact_string = "a" * 200
        result = _validate_string_length(exact_string, "name", 200)
        assert len(result) == 200

    def test_non_string_converted(self) -> None:
        """Non-string values should be converted."""
        result = _validate_string_length(123, "field", 200)
        assert result == "123"


class TestValidateUrl:
    """Tests for URL validation."""

    def test_valid_https_url(self) -> None:
        """Valid HTTPS URL should pass."""
        url = "https://example.com/image.png"
        result = _validate_url(url)
        assert result == url

    def test_valid_http_url(self) -> None:
        """Valid HTTP URL should pass."""
        url = "http://example.com/image.png"
        result = _validate_url(url)
        assert result == url

    def test_invalid_scheme(self) -> None:
        """Invalid scheme should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_url("ftp://example.com/file.txt")
        assert "must use http or https scheme" in str(exc_info.value)

    def test_javascript_scheme_blocked(self) -> None:
        """JavaScript URLs should be blocked."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_url("javascript:alert(1)")
        assert "must use http or https scheme" in str(exc_info.value)

    def test_data_scheme_blocked(self) -> None:
        """Data URLs should be blocked."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_url("data:text/html,<script>alert(1)</script>")
        assert "must use http or https scheme" in str(exc_info.value)

    def test_missing_domain(self) -> None:
        """URL without domain should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_url("https:///path")
        assert "must have a valid domain" in str(exc_info.value)

    def test_url_too_long(self) -> None:
        """URL exceeding max length should raise error."""
        long_url = "https://example.com/" + "a" * 3000
        with pytest.raises(ValidationError) as exc_info:
            _validate_url(long_url)
        assert f"must be at most {MAX_URL_LENGTH}" in str(exc_info.value)


class TestValidateMediaUrls:
    """Tests for media URLs validation."""

    def test_valid_urls(self) -> None:
        """Valid URLs should pass."""
        urls = [
            "https://example.com/image1.png",
            "https://example.com/image2.jpg",
        ]
        result = _validate_media_urls(urls)
        assert len(result) == 2

    def test_empty_list(self) -> None:
        """Empty list should pass."""
        result = _validate_media_urls([])
        assert result == []

    def test_too_many_urls(self) -> None:
        """Too many URLs should raise error."""
        urls = [f"https://example.com/img{i}.png" for i in range(25)]
        with pytest.raises(ValidationError) as exc_info:
            _validate_media_urls(urls)
        assert f"cannot have more than {MAX_MEDIA_URLS_COUNT}" in str(exc_info.value)

    def test_invalid_url_in_list(self) -> None:
        """Invalid URL in list should raise error."""
        urls = [
            "https://example.com/valid.png",
            "javascript:alert(1)",
        ]
        with pytest.raises(ValidationError) as exc_info:
            _validate_media_urls(urls)
        assert "must use http or https scheme" in str(exc_info.value)

    def test_empty_strings_filtered(self) -> None:
        """Empty strings should be filtered out."""
        urls = ["https://example.com/image.png", "", "  "]
        result = _validate_media_urls(urls)
        assert len(result) == 1


class TestValidateLogoMediaUrl:
    """Tests for logo_media_url validation."""

    def test_none_logo_allowed(self) -> None:
        """None logo should return None."""
        result = _validate_logo_media_url(None, [])
        assert result is None

    def test_valid_logo_in_media_list(self) -> None:
        """Logo must match one of the media URLs."""
        urls = [
            "https://example.com/image.png",
            "https://example.com/cover.png",
        ]
        result = _validate_logo_media_url(urls[1], urls)
        assert result == urls[1]

    def test_logo_not_in_list_raises(self) -> None:
        """Logo not in media_urls should raise error."""
        urls = ["https://example.com/image.png"]
        with pytest.raises(ValidationError) as exc_info:
            _validate_logo_media_url("https://example.com/other.png", urls)
        assert "logo_media_url must match one of media_urls" in str(exc_info.value)


class TestValidateCurrency:
    """Tests for currency code validation."""

    def test_valid_currency_codes(self) -> None:
        """Valid currency codes should pass."""
        assert _validate_currency("HKD") == "HKD"
        assert _validate_currency("USD") == "USD"
        assert _validate_currency("EUR") == "EUR"
        assert _validate_currency("AED") == "AED"

    def test_lowercase_normalized(self) -> None:
        """Lowercase codes should be normalized to uppercase."""
        assert _validate_currency("hkd") == "HKD"
        assert _validate_currency("usd") == "USD"

    def test_default_currency(self) -> None:
        """Empty/None should return default HKD."""
        assert _validate_currency("") == "HKD"
        assert _validate_currency(None) == "HKD"

    def test_invalid_currency(self) -> None:
        """Invalid currency code should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_currency("ZZZ")
        assert "valid ISO 4217 code" in str(exc_info.value)

    def test_sql_injection_attempt(self) -> None:
        """SQL injection attempt should be blocked."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_currency("HKD'; DROP TABLE--")
        assert "valid ISO 4217 code" in str(exc_info.value)


class TestValidateLanguageCode:
    """Tests for language code validation."""

    def test_valid_language_codes(self) -> None:
        """Valid language codes should pass."""
        assert _validate_language_code("en") == "en"
        assert _validate_language_code("zh") == "zh"
        assert _validate_language_code("ja") == "ja"

    def test_uppercase_normalized(self) -> None:
        """Uppercase codes should be normalized to lowercase."""
        assert _validate_language_code("EN") == "en"
        assert _validate_language_code("ZH") == "zh"

    def test_cantonese_code(self) -> None:
        """Cantonese code should be valid."""
        assert _validate_language_code("yue") == "yue"

    def test_invalid_language_code(self) -> None:
        """Invalid language code should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_language_code("invalid")
        assert "valid ISO 639-1 language code" in str(exc_info.value)

    def test_empty_language_code(self) -> None:
        """Empty language code should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_language_code("")
        assert "cannot be empty" in str(exc_info.value)


class TestValidateLanguages:
    """Tests for languages list validation."""

    def test_valid_languages(self) -> None:
        """Valid language list should pass."""
        result = _validate_languages(["en", "zh", "ja"])
        assert result == ["en", "zh", "ja"]

    def test_empty_list(self) -> None:
        """Empty list should pass."""
        result = _validate_languages([])
        assert result == []

    def test_duplicates_removed(self) -> None:
        """Duplicate languages should be removed."""
        result = _validate_languages(["en", "zh", "en", "zh"])
        assert result == ["en", "zh"]

    def test_too_many_languages(self) -> None:
        """Too many languages should raise error."""
        languages = ["en"] * 25
        with pytest.raises(ValidationError) as exc_info:
            _validate_languages(languages)
        assert f"cannot have more than {MAX_LANGUAGES_COUNT}" in str(exc_info.value)

    def test_empty_strings_filtered(self) -> None:
        """Empty strings should be filtered out."""
        result = _validate_languages(["en", "", "zh", "  "])
        assert result == ["en", "zh"]


class TestLikePatternEscape:
    """Tests for LIKE pattern escaping in repositories."""

    def test_escape_function_exists(self) -> None:
        """Escape function should be available."""
        from app.db.repositories.organization import _escape_like_pattern

        # Test basic escaping
        assert _escape_like_pattern("test") == "test"
        assert _escape_like_pattern("test%") == "test\\%"
        assert _escape_like_pattern("test_name") == "test\\_name"
        assert _escape_like_pattern("100%") == "100\\%"

    def test_escape_all_special_chars(self) -> None:
        """All LIKE special characters should be escaped."""
        from app.db.repositories.organization import _escape_like_pattern

        result = _escape_like_pattern("a%b_c\\d")
        assert result == "a\\%b\\_c\\\\d"

    def test_escape_injection_attempt(self) -> None:
        """SQL injection attempts should be escaped."""
        from app.db.repositories.activity import _escape_like_pattern

        # This would match everything without escaping
        result = _escape_like_pattern("%")
        assert result == "\\%"

        # This is a common injection pattern
        result = _escape_like_pattern("'; DROP TABLE--")
        assert result == "'; DROP TABLE--"  # No special LIKE chars

        result = _escape_like_pattern("test%' OR '1'='1")
        assert result == "test\\%' OR '1'='1"

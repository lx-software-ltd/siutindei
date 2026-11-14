"""Tests for admin validation logic (locations, activities, pricing)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.api.admin_resource_activity import _validate_age_range  # noqa: E402
from app.api.admin_resource_location import _validate_coordinates  # noqa: E402
from app.api.admin_resource_pricing import (  # noqa: E402
    _validate_pricing_amount,
    _validate_sessions_count,
)
from app.api.admin_validators import (  # noqa: E402
    _validate_email,
    _validate_manager_id,
    _validate_phone_fields,
    _validate_social_value,
)
from app.exceptions import ValidationError  # noqa: E402


class TestValidateCoordinates:
    """Tests for location coordinate validation."""

    def test_valid_coordinates(self) -> None:
        """Valid coordinates should pass validation."""
        _validate_coordinates(22.28, 114.16)  # Hong Kong
        _validate_coordinates(-33.87, 151.21)  # Sydney
        _validate_coordinates(0, 0)  # Null Island
        _validate_coordinates(None, None)  # Both optional

    def test_valid_boundary_coordinates(self) -> None:
        """Boundary coordinates should pass validation."""
        _validate_coordinates(-90, -180)
        _validate_coordinates(90, 180)
        _validate_coordinates(-90, 180)
        _validate_coordinates(90, -180)

    def test_lat_below_range(self) -> None:
        """Latitude below -90 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_coordinates(-91, 0)
        assert "lat must be between -90 and 90" in str(exc_info.value)
        assert exc_info.value.field == "lat"

    def test_lat_above_range(self) -> None:
        """Latitude above 90 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_coordinates(91, 0)
        assert "lat must be between -90 and 90" in str(exc_info.value)
        assert exc_info.value.field == "lat"

    def test_lng_below_range(self) -> None:
        """Longitude below -180 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_coordinates(0, -181)
        assert "lng must be between -180 and 180" in str(exc_info.value)
        assert exc_info.value.field == "lng"

    def test_lng_above_range(self) -> None:
        """Longitude above 180 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_coordinates(0, 181)
        assert "lng must be between -180 and 180" in str(exc_info.value)
        assert exc_info.value.field == "lng"

    def test_lat_invalid_type(self) -> None:
        """Non-numeric latitude should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_coordinates("invalid", 0)
        assert "lat must be a valid number" in str(exc_info.value)
        assert exc_info.value.field == "lat"

    def test_lng_invalid_type(self) -> None:
        """Non-numeric longitude should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_coordinates(0, "invalid")
        assert "lng must be a valid number" in str(exc_info.value)
        assert exc_info.value.field == "lng"

    def test_lat_only_valid(self) -> None:
        """Valid latitude with None longitude should pass."""
        _validate_coordinates(45.0, None)

    def test_lng_only_valid(self) -> None:
        """Valid longitude with None latitude should pass."""
        _validate_coordinates(None, 90.0)

    def test_string_numbers_valid(self) -> None:
        """String representations of numbers should be valid."""
        _validate_coordinates("22.28", "114.16")
        _validate_coordinates("-90", "-180")


class TestValidateAgeRange:
    """Tests for activity age range validation."""

    def test_valid_age_range(self) -> None:
        """Valid age ranges should pass validation."""
        _validate_age_range(0, 5)
        _validate_age_range(5, 12)
        _validate_age_range(0, 18)
        _validate_age_range(17, 18)

    def test_age_min_negative(self) -> None:
        """Negative age_min should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_age_range(-1, 10)
        assert "age_min must be at least 0" in str(exc_info.value)
        assert exc_info.value.field == "age_min"

    def test_age_above_18_is_stored_as_18(self) -> None:
        """A maximum or minimum over 18 is capped, including a single age."""
        assert _validate_age_range(0, 19) == (0, 18)
        assert _validate_age_range(5, 100) == (5, 18)
        assert _validate_age_range(20, 40) == (18, 18)

    def test_age_min_equals_age_max(self) -> None:
        """A single age is a valid range."""
        assert _validate_age_range(10, 10) == (10, 10)
        assert _validate_age_range(0, 0) == (0, 0)

    def test_age_min_greater_than_age_max(self) -> None:
        """age_min above age_max should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_age_range(15, 10)
        assert "age_min cannot exceed age_max" in str(exc_info.value)
        assert exc_info.value.field == "age_min"

    def test_age_invalid_type(self) -> None:
        """Non-integer age values should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_age_range("invalid", 10)
        assert "age_min and age_max must be valid integers" in str(exc_info.value)

    def test_string_numbers_valid(self) -> None:
        """String representations of integers should be valid."""
        _validate_age_range("5", "12")

    def test_boundary_values(self) -> None:
        """Boundary values (0, 18) should be valid."""
        _validate_age_range(0, 1)
        _validate_age_range(17, 18)


class TestValidatePricingAmount:
    """Tests for pricing amount validation."""

    def test_valid_amounts(self) -> None:
        """Valid amounts should pass validation."""
        _validate_pricing_amount(0)
        _validate_pricing_amount(100)
        _validate_pricing_amount(150.50)
        _validate_pricing_amount("99.99")
        _validate_pricing_amount(Decimal("1000.00"))

    def test_negative_amount(self) -> None:
        """Negative amount should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_pricing_amount(-1)
        assert "amount must be at least 0" in str(exc_info.value)
        assert exc_info.value.field == "amount"

    def test_negative_decimal_amount(self) -> None:
        """Negative decimal amount should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_pricing_amount(-0.01)
        assert "amount must be at least 0" in str(exc_info.value)
        assert exc_info.value.field == "amount"

    def test_invalid_amount_type(self) -> None:
        """Non-numeric amount should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_pricing_amount("invalid")
        assert "amount must be a valid number" in str(exc_info.value)
        assert exc_info.value.field == "amount"

    def test_zero_amount_valid(self) -> None:
        """Zero amount should be valid (free activities)."""
        _validate_pricing_amount(0)
        _validate_pricing_amount("0")
        _validate_pricing_amount(0.00)


class TestValidateSessionsCount:
    """Tests for sessions count validation."""

    def test_valid_sessions_count(self) -> None:
        """Valid sessions counts should pass validation."""
        _validate_sessions_count(1)
        _validate_sessions_count(5)
        _validate_sessions_count(100)
        _validate_sessions_count("10")

    def test_zero_sessions_count(self) -> None:
        """Zero sessions count should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_sessions_count(0)
        assert "sessions_count must be greater than 0" in str(exc_info.value)
        assert exc_info.value.field == "sessions_count"

    def test_negative_sessions_count(self) -> None:
        """Negative sessions count should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_sessions_count(-1)
        assert "sessions_count must be greater than 0" in str(exc_info.value)
        assert exc_info.value.field == "sessions_count"

    def test_invalid_sessions_count_type(self) -> None:
        """Non-integer sessions count should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_sessions_count("invalid")
        assert "sessions_count must be a valid integer" in str(exc_info.value)
        assert exc_info.value.field == "sessions_count"

    def test_float_sessions_count(self) -> None:
        """Float that converts to valid integer should work."""
        _validate_sessions_count(5.0)  # int(5.0) = 5


class TestValidateManagerId:
    """Tests for organization manager_id (Cognito user sub) validation."""

    def test_valid_manager_id(self) -> None:
        """Valid UUID manager_id should pass validation."""
        test_uuid = str(uuid4())
        result = _validate_manager_id(test_uuid)
        assert result == test_uuid

    def test_valid_manager_id_uppercase(self) -> None:
        """Uppercase UUID should be normalized."""
        test_uuid = str(uuid4()).upper()
        result = _validate_manager_id(test_uuid)
        assert result is not None
        # Result should be lowercase UUID format
        assert result == test_uuid.lower()

    def test_none_manager_id(self) -> None:
        """None manager_id should return None when not required."""
        result = _validate_manager_id(None)
        assert result is None

    def test_none_manager_id_required(self) -> None:
        """None manager_id should raise ValidationError when required."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_manager_id(None, required=True)
        assert "manager_id is required" in str(exc_info.value)
        assert exc_info.value.field == "manager_id"

    def test_empty_string_manager_id(self) -> None:
        """Empty string manager_id should return None when not required."""
        result = _validate_manager_id("")
        assert result is None

    def test_empty_string_manager_id_required(self) -> None:
        """Empty string manager_id should raise ValidationError when required."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_manager_id("", required=True)
        assert "manager_id is required" in str(exc_info.value)
        assert exc_info.value.field == "manager_id"

    def test_whitespace_only_manager_id(self) -> None:
        """Whitespace-only manager_id should return None when not required."""
        result = _validate_manager_id("   ")
        assert result is None

    def test_whitespace_only_manager_id_required(self) -> None:
        """Whitespace-only manager_id should raise ValidationError when required."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_manager_id("   ", required=True)
        assert "manager_id is required" in str(exc_info.value)
        assert exc_info.value.field == "manager_id"

    def test_invalid_uuid_format(self) -> None:
        """Invalid UUID format should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_manager_id("not-a-valid-uuid")
        assert "manager_id must be a valid UUID" in str(exc_info.value)
        assert exc_info.value.field == "manager_id"

    def test_uuid_with_whitespace(self) -> None:
        """UUID with surrounding whitespace should be trimmed and valid."""
        test_uuid = str(uuid4())
        result = _validate_manager_id(f"  {test_uuid}  ")
        assert result == test_uuid

    def test_sql_injection_attempt(self) -> None:
        """SQL injection attempt should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_manager_id("'; DROP TABLE organizations; --")
        assert "manager_id must be a valid UUID" in str(exc_info.value)

    def test_non_string_convertible(self) -> None:
        """Non-string that can be converted should work if valid UUID."""
        # UUID object passed directly
        test_uuid = uuid4()
        result = _validate_manager_id(test_uuid)
        assert result == str(test_uuid)

    def test_valid_manager_id_required(self) -> None:
        """Valid UUID manager_id with required=True should pass validation."""
        test_uuid = str(uuid4())
        result = _validate_manager_id(test_uuid, required=True)
        assert result == test_uuid


class TestValidateEmail:
    """Tests for email validation."""

    def test_valid_email(self) -> None:
        """Valid email should pass."""
        assert _validate_email("admin@example.com") == "admin@example.com"

    def test_invalid_email(self) -> None:
        """Invalid email should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_email("not-an-email")
        assert "email must be a valid email address" in str(exc_info.value)
        assert exc_info.value.field == "email"

    def test_empty_email(self) -> None:
        """Empty email should return None."""
        assert _validate_email("") is None


class TestValidatePhoneFields:
    """Tests for phone field validation."""

    def test_valid_phone_fields_hk(self) -> None:
        """Valid HK phone should pass."""
        code, number = _validate_phone_fields("HK", "9123 4567")
        assert code == "HK"
        assert number == "91234567"

    def test_missing_country_code(self) -> None:
        """Missing country code should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_phone_fields(None, "91234567")
        assert "phone_country_code is required" in str(exc_info.value)
        assert exc_info.value.field == "phone_country_code"

    def test_missing_phone_number(self) -> None:
        """Missing phone number should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_phone_fields("HK", None)
        assert "phone_number is required" in str(exc_info.value)
        assert exc_info.value.field == "phone_number"

    def test_invalid_country_code(self) -> None:
        """Invalid country code should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_phone_fields("ZZ", "91234567")
        assert "phone_country_code must be a valid ISO country code" in str(
            exc_info.value
        )
        assert exc_info.value.field == "phone_country_code"

    def test_invalid_phone_number(self) -> None:
        """Invalid phone number should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_phone_fields("HK", "1234")
        assert "phone_number is not valid" in str(exc_info.value)
        assert exc_info.value.field == "phone_number"


class TestValidateSocialValue:
    """Tests for social handle/URL validation."""

    def test_valid_handle(self) -> None:
        """Valid handles should pass."""
        assert _validate_social_value("@example_user", "instagram") == "@example_user"
        assert _validate_social_value("example.user", "twitter") == "example.user"

    def test_valid_url(self) -> None:
        """Valid URLs should pass."""
        assert (
            _validate_social_value("https://example.com/user", "facebook")
            == "https://example.com/user"
        )

    def test_invalid_handle(self) -> None:
        """Invalid handles should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_social_value("bad handle", "whatsapp")
        assert "whatsapp must be a valid handle or URL" in str(exc_info.value)
        assert exc_info.value.field == "whatsapp"

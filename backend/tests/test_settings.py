import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings


def test_settings_load_without_defaults() -> None:
    loaded_settings = Settings()  # pyright: ignore[reportCallIssue]
    assert loaded_settings.database_url
    assert loaded_settings.cors_origins
    assert loaded_settings.currency == "NGN"
    assert loaded_settings.business_timezone == "Africa/Lagos"
    assert loaded_settings.auth0_roles_claim
    assert loaded_settings.owner_notification_email


def test_currency_and_business_timezone_are_read_from_the_environment() -> None:
    assert settings.currency == "NGN"
    assert settings.business_timezone == "Africa/Lagos"
    assert settings.auth0_roles_claim
    assert settings.owner_notification_email


@pytest.mark.parametrize("currency", ["NG", "NGNX", "N1N", "naira", "  NG  "])
def test_invalid_currency_fails_validation(currency: str) -> None:
    with pytest.raises(ValidationError, match="CURRENCY must be a 3-letter"):
        Settings(currency=currency)  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    "business_timezone",
    ["Lagos", "Africa/Atlantis", "utc+1", ""],
)
def test_invalid_business_timezone_fails_validation(business_timezone: str) -> None:
    with pytest.raises(ValidationError, match="BUSINESS_TIMEZONE must be a valid IANA"):
        Settings(business_timezone=business_timezone)  # pyright: ignore[reportCallIssue]


def test_a_missing_setting_fails_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OWNER_NOTIFICATION_EMAIL")
    with pytest.raises(ValidationError, match="owner_notification_email"):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

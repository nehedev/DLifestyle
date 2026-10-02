from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    database_url: str
    redis_url: str
    auth0_domain: str
    auth0_audience: str
    auth0_email_claim: str
    auth0_first_name_claim: str
    auth0_last_name_claim: str
    auth0_roles_claim: str
    jwks_cache_ttl_seconds: int
    jwks_timeout_seconds: int
    currency: str
    business_timezone: str
    payment_provider: str
    paystack_secret_key: SecretStr
    paystack_connect_timeout_seconds: int
    paystack_timeout_seconds: int
    payment_callback_url: str
    cors_origins: list[str]
    resend_api_key: SecretStr
    resend_connect_timeout_seconds: int
    resend_timeout_seconds: int
    email_from_address: str
    owner_notification_email: str
    pending_order_timeout_minutes: int
    expiry_job_interval_minutes: int
    celery_task_max_retries: int
    celery_retry_backoff_max_seconds: int

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str) -> str:
        if not value.isascii() or not value.isalpha() or len(value) != 3:
            raise ValueError("CURRENCY must be a 3-letter currency code")
        return value

    @field_validator("business_timezone")
    @classmethod
    def check_business_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(
                "BUSINESS_TIMEZONE must be a valid IANA timezone name"
            ) from error
        return value


settings = Settings()  # pyright: ignore[reportCallIssue]

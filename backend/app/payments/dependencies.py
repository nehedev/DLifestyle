from app.core.config import settings
from app.payments.paystack import PaystackProvider
from app.payments.protocol import PaymentProvider


def get_payment_provider() -> PaymentProvider:
    if settings.payment_provider == PaystackProvider.name:
        return PaystackProvider()
    raise RuntimeError("Unsupported payment provider")

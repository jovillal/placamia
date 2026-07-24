import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from urllib.parse import parse_qsl, urlparse

import pytest
from app.domain.payment_provider_gateway import CheckoutRequest
from app.services.payment_provider_registry import (
    ConfiguredPaymentProviderRuntimeFactory,
    PaymentProviderConfigurationError,
)
from app.services.wompi_payment_provider import (
    InvalidPaymentAmount,
    PaymentProviderHandoffError,
    UnsupportedPaymentCurrency,
    WompiPaymentProvider,
)


def checkout_request(
    *,
    amount: Decimal = Decimal("85000.00"),
    currency: str = "COP",
    return_url: str = "http://localhost:3000/payments/return",
) -> CheckoutRequest:
    """Return one deterministic backend-owned Wompi checkout request."""
    return CheckoutRequest(
        merchant_reference="placamia-payment-123",
        amount=amount,
        currency=currency,
        customer_email="buyer@example.com",
        return_url=return_url,
        expires_at=datetime(2026, 7, 22, 18, 30, tzinfo=UTC),
    )


def test_wompi_checkout_uses_exact_signed_redirect_contract():
    secret = "test_integrity_contract-secret"
    provider = WompiPaymentProvider(
        public_key="pub_test_contract-key",
        integrity_secret=secret,
        approved_return_url="http://localhost:3000/payments/return",
    )

    session = asyncio.run(provider.initialize_checkout(checkout_request()))

    parsed_url = urlparse(session.handoff.url)
    query_items = parse_qsl(parsed_url.query, keep_blank_values=True)
    expiration = "2026-07-22T18:30:00.000Z"
    signature_preimage = f"placamia-payment-1238500000COP{expiration}{secret}"
    expected_signature = sha256(signature_preimage.encode("utf-8")).hexdigest()

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "checkout.wompi.co"
    assert parsed_url.path == "/p/"
    assert [key for key, _value in query_items] == [
        "public-key",
        "currency",
        "amount-in-cents",
        "reference",
        "signature:integrity",
        "redirect-url",
        "expiration-time",
    ]
    assert dict(query_items) == {
        "public-key": "pub_test_contract-key",
        "currency": "COP",
        "amount-in-cents": "8500000",
        "reference": "placamia-payment-123",
        "signature:integrity": expected_signature,
        "redirect-url": "http://localhost:3000/payments/return",
        "expiration-time": expiration,
    }
    assert session.merchant_reference == "placamia-payment-123"
    assert session.provider_checkout_reference is None
    assert session.expires_at == checkout_request().expires_at
    assert "buyer@example.com" not in session.handoff.url


@pytest.mark.parametrize(
    ("amount", "expected_exception"),
    [
        (Decimal("0"), InvalidPaymentAmount),
        (Decimal("-1.00"), InvalidPaymentAmount),
        (Decimal("1.001"), InvalidPaymentAmount),
    ],
)
def test_wompi_checkout_rejects_invalid_amount_without_rounding(
    amount,
    expected_exception,
):
    provider = WompiPaymentProvider(
        public_key="pub_test_contract-key",
        integrity_secret="test_integrity_contract-secret",
        approved_return_url="http://localhost:3000/payments/return",
    )

    with pytest.raises(expected_exception):
        asyncio.run(provider.initialize_checkout(checkout_request(amount=amount)))


def test_wompi_checkout_rejects_non_cop_currency():
    provider = WompiPaymentProvider(
        public_key="pub_test_contract-key",
        integrity_secret="test_integrity_contract-secret",
        approved_return_url="http://localhost:3000/payments/return",
    )

    with pytest.raises(UnsupportedPaymentCurrency):
        asyncio.run(provider.initialize_checkout(checkout_request(currency="USD")))


def test_wompi_checkout_rejects_caller_return_url_override():
    provider = WompiPaymentProvider(
        public_key="pub_test_contract-key",
        integrity_secret="test_integrity_contract-secret",
        approved_return_url="http://localhost:3000/payments/return",
    )

    with pytest.raises(PaymentProviderHandoffError):
        asyncio.run(
            provider.initialize_checkout(
                checkout_request(return_url="https://attacker.example/return")
            )
        )


class StubSettings:
    """Minimal settings object used to contract-test provider configuration."""

    PAYMENT_PROVIDER_DEFAULT = "wompi"
    PAYMENT_RETURN_URL = "http://localhost:3000/payments/return"
    PAYMENT_CHECKOUT_TTL_SECONDS = "1800"
    WOMPI_ENVIRONMENT = "sandbox"
    WOMPI_PUBLIC_KEY = "pub_test_contract-key"
    WOMPI_INTEGRITY_SECRET = "test_integrity_contract-secret"


def test_provider_runtime_factory_builds_valid_sandbox_runtime():
    runtime = ConfiguredPaymentProviderRuntimeFactory(StubSettings()).create()

    provider_code, provider = runtime.registry.get_default()

    assert provider_code == "wompi"
    assert isinstance(provider, WompiPaymentProvider)
    assert runtime.checkout_ttl_seconds == 1800
    assert runtime.return_url == "http://localhost:3000/payments/return"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("PAYMENT_RETURN_URL", "http://payments.example.com/return"),
        ("PAYMENT_RETURN_URL", "relative/return"),
        ("PAYMENT_RETURN_URL", "https:///return"),
        ("PAYMENT_RETURN_URL", "https://user@example.com/return"),
        ("PAYMENT_RETURN_URL", "https://example.com/return#fragment"),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", None),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", "0"),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", "-1"),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", "1799"),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", "1801"),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", "not-an-integer"),
        ("WOMPI_ENVIRONMENT", "unknown"),
        ("WOMPI_PUBLIC_KEY", "pub_prod_wrong-environment"),
        ("WOMPI_INTEGRITY_SECRET", "prod_integrity_wrong-environment"),
    ],
)
def test_provider_runtime_factory_rejects_invalid_configuration(field, value):
    settings = StubSettings()
    setattr(settings, field, value)

    with pytest.raises(PaymentProviderConfigurationError):
        ConfiguredPaymentProviderRuntimeFactory(settings).create()


def test_provider_runtime_factory_accepts_production_prefixes_and_https():
    settings = StubSettings()
    settings.PAYMENT_RETURN_URL = "https://placamia.example/payments/return"
    settings.WOMPI_ENVIRONMENT = "production"
    settings.WOMPI_PUBLIC_KEY = "pub_prod_contract-key"
    settings.WOMPI_INTEGRITY_SECRET = "prod_integrity_contract-secret"

    runtime = ConfiguredPaymentProviderRuntimeFactory(settings).create()

    assert runtime.return_url == "https://placamia.example/payments/return"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("WOMPI_PUBLIC_KEY", "pub_test_wrong-environment"),
        ("WOMPI_INTEGRITY_SECRET", "test_integrity_wrong-environment"),
    ],
)
def test_production_rejects_sandbox_key_prefixes(field, value):
    settings = StubSettings()
    settings.PAYMENT_RETURN_URL = "https://placamia.example/payments/return"
    settings.WOMPI_ENVIRONMENT = "production"
    settings.WOMPI_PUBLIC_KEY = "pub_prod_contract-key"
    settings.WOMPI_INTEGRITY_SECRET = "prod_integrity_contract-secret"
    setattr(settings, field, value)

    with pytest.raises(PaymentProviderConfigurationError):
        ConfiguredPaymentProviderRuntimeFactory(settings).create()


def test_sandbox_accepts_loopback_http_return_url():
    settings = StubSettings()
    settings.PAYMENT_RETURN_URL = "http://127.0.0.1:3000/payments/return"

    runtime = ConfiguredPaymentProviderRuntimeFactory(settings).create()

    assert runtime.return_url == settings.PAYMENT_RETURN_URL


def test_sandbox_and_production_use_same_fixed_checkout_host():
    sandbox_runtime = ConfiguredPaymentProviderRuntimeFactory(StubSettings()).create()
    production_settings = StubSettings()
    production_settings.PAYMENT_RETURN_URL = "https://placamia.example/payments/return"
    production_settings.WOMPI_ENVIRONMENT = "production"
    production_settings.WOMPI_PUBLIC_KEY = "pub_prod_contract-key"
    production_settings.WOMPI_INTEGRITY_SECRET = "prod_integrity_contract-secret"
    production_runtime = ConfiguredPaymentProviderRuntimeFactory(
        production_settings
    ).create()

    sandbox_session = asyncio.run(
        sandbox_runtime.registry.get("wompi").initialize_checkout(checkout_request())
    )
    production_session = asyncio.run(
        production_runtime.registry.get("wompi").initialize_checkout(
            checkout_request(return_url=production_settings.PAYMENT_RETURN_URL)
        )
    )

    assert urlparse(sandbox_session.handoff.url).netloc == "checkout.wompi.co"
    assert urlparse(production_session.handoff.url).netloc == "checkout.wompi.co"


@pytest.mark.parametrize("default_provider_code", [None, "", "legacy_generic"])
def test_registry_rejects_invalid_default_only_when_new_payment_requests_it(
    default_provider_code,
):
    settings = StubSettings()
    settings.PAYMENT_PROVIDER_DEFAULT = default_provider_code

    runtime = ConfiguredPaymentProviderRuntimeFactory(settings).create()

    with pytest.raises(LookupError):
        runtime.registry.get_default()
    assert isinstance(runtime.registry.get("wompi"), WompiPaymentProvider)

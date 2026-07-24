from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import urlsplit

from app.domain.payment_provider_gateway import PaymentProviderGateway
from app.services.wompi_payment_provider import WompiPaymentProvider

WOMPI_PROVIDER_CODE = "wompi"
SUPPORTED_WOMPI_ENVIRONMENTS = frozenset({"sandbox", "production"})
WOMPI_KEY_PREFIXES = {
    "sandbox": ("pub_test_", "test_integrity_"),
    "production": ("pub_prod_", "prod_integrity_"),
}
LOCAL_RETURN_HOSTS = frozenset({"localhost", "127.0.0.1"})
REQUIRED_CHECKOUT_TTL_SECONDS = 1800


class PaymentProviderConfigurationError(RuntimeError):
    """Raised when payment provider configuration fails closed."""


class UnsupportedPaymentProvider(LookupError):
    """Raised when no adapter is registered for a provider code."""


class PaymentProviderRegistry:
    """Resolve payment-provider adapters without applying business rules."""

    def __init__(
        self,
        providers: Mapping[str, PaymentProviderGateway],
        default_provider_code: str | None,
    ) -> None:
        """Store registered adapters and the configured default code."""
        self._providers = dict(providers)
        self._default_provider_code = default_provider_code

    def get(self, provider_code: str) -> PaymentProviderGateway:
        """Return the adapter registered for one persisted provider code."""
        try:
            return self._providers[provider_code]
        except KeyError as exc:
            raise UnsupportedPaymentProvider(provider_code) from exc

    def get_default(self) -> tuple[str, PaymentProviderGateway]:
        """Return the configured adapter used only for new Payments."""
        provider_code = self._default_provider_code
        if not isinstance(provider_code, str) or not provider_code:
            raise UnsupportedPaymentProvider("")
        return provider_code, self.get(provider_code)


@dataclass(frozen=True)
class PaymentProviderRuntime:
    """Validated provider registry plus application checkout configuration."""

    registry: PaymentProviderRegistry
    return_url: str
    checkout_ttl_seconds: int


class PaymentProviderRuntimeFactory(Protocol):
    """Build provider runtime configuration after owner-scoped Order lookup."""

    def create(self) -> PaymentProviderRuntime:
        """Validate configuration and return the payment-provider runtime."""


class ConfiguredPaymentProviderRuntimeFactory:
    """Create the Wompi provider runtime from process settings on demand."""

    def __init__(self, settings: object) -> None:
        """Store settings without evaluating payment-provider configuration."""
        self._settings = settings

    def create(self) -> PaymentProviderRuntime:
        """Validate all MVP Wompi configuration and build the registry.

        Returns:
            Runtime containing the Wompi registry, return URL, and fixed TTL.

        Raises:
            PaymentProviderConfigurationError: If any required value is
                missing, malformed, unsafe, or inconsistent.

        Side effects:
            Reads configured values. It performs no network or persistence
            operation and does not log credentials.
        """
        environment = _required_text(self._settings, "WOMPI_ENVIRONMENT")
        if environment not in SUPPORTED_WOMPI_ENVIRONMENTS:
            raise PaymentProviderConfigurationError(
                "Payment provider configuration is unavailable."
            )

        public_key = _required_text(self._settings, "WOMPI_PUBLIC_KEY")
        integrity_secret = _required_text(
            self._settings,
            "WOMPI_INTEGRITY_SECRET",
        )
        public_prefix, integrity_prefix = WOMPI_KEY_PREFIXES[environment]
        if not public_key.startswith(public_prefix) or not integrity_secret.startswith(
            integrity_prefix
        ):
            raise PaymentProviderConfigurationError(
                "Payment provider configuration is unavailable."
            )

        return_url = _required_text(self._settings, "PAYMENT_RETURN_URL")
        _validate_return_url(return_url, environment)
        checkout_ttl_seconds = _checkout_ttl_seconds(self._settings)
        default_provider_code = getattr(
            self._settings,
            "PAYMENT_PROVIDER_DEFAULT",
            None,
        )

        provider = WompiPaymentProvider(
            public_key=public_key,
            integrity_secret=integrity_secret,
            approved_return_url=return_url,
        )
        registry = PaymentProviderRegistry(
            {WOMPI_PROVIDER_CODE: provider},
            default_provider_code,
        )
        return PaymentProviderRuntime(
            registry=registry,
            return_url=return_url,
            checkout_ttl_seconds=checkout_ttl_seconds,
        )


def _required_text(settings: object, field: str) -> str:
    """Return one non-blank configured string without exposing its value."""
    value = getattr(settings, field, None)
    if not isinstance(value, str) or not value.strip():
        raise PaymentProviderConfigurationError(
            "Payment provider configuration is unavailable."
        )
    return value.strip()


def _checkout_ttl_seconds(settings: object) -> int:
    """Return the fixed MVP checkout TTL or fail closed."""
    raw_value = getattr(settings, "PAYMENT_CHECKOUT_TTL_SECONDS", None)
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise PaymentProviderConfigurationError(
            "Payment provider configuration is unavailable."
        ) from exc
    if value != REQUIRED_CHECKOUT_TTL_SECONDS:
        raise PaymentProviderConfigurationError(
            "Payment provider configuration is unavailable."
        )
    return value


def _validate_return_url(return_url: str, environment: str) -> None:
    """Reject unsafe or structurally invalid customer return URLs."""
    parsed = urlsplit(return_url)
    if (
        not parsed.scheme
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise PaymentProviderConfigurationError(
            "Payment provider configuration is unavailable."
        )
    if parsed.scheme == "https":
        return
    if (
        environment == "sandbox"
        and parsed.scheme == "http"
        and parsed.hostname in LOCAL_RETURN_HOSTS
    ):
        return
    raise PaymentProviderConfigurationError(
        "Payment provider configuration is unavailable."
    )

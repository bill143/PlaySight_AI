"""Storefront adapter protocol and registry for catalog/inventory sync.

Adapters bridge the PlaySight catalog with external storefronts (Shopify,
WooCommerce). Phase 2 ships protocol stubs only; real API integrations are
# TODO(phase2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from playsight.core.errors import ValidationFailed


@dataclass(frozen=True)
class ExternalVariant:
    """A product variant as represented by an external storefront."""

    external_id: str
    sku: str
    size: str | None = None
    color: str | None = None
    price_cents: int | None = None
    inventory_qty: int = 0


@dataclass(frozen=True)
class ExternalProduct:
    """A product as represented by an external storefront."""

    external_id: str
    name: str
    description: str = ""
    base_price_cents: int = 0
    currency: str = "USD"
    variants: tuple[ExternalVariant, ...] = ()


@runtime_checkable
class MerchandiseAdapter(Protocol):
    """Protocol every storefront adapter must satisfy.

    Attributes:
        key: Unique registry key (e.g. ``"shopify"``, ``"woocommerce"``).
    """

    key: str

    def fetch_products(self, config: Mapping[str, Any]) -> list[ExternalProduct]:
        """Fetch the external catalog for the given store configuration."""
        ...

    def push_inventory(self, config: Mapping[str, Any], sku: str, quantity: int) -> None:
        """Push an absolute inventory quantity for ``sku`` to the storefront."""
        ...


_REGISTRY: dict[str, MerchandiseAdapter] = {}


def register_adapter(adapter: MerchandiseAdapter) -> MerchandiseAdapter:
    """Register an adapter instance under its ``key`` and return it.

    Raises:
        ValueError: If the adapter has no ``key`` or the key is already taken
            by a different adapter instance.
    """
    if not getattr(adapter, "key", None):
        raise ValueError("Merchandise adapter must define a non-empty 'key'.")
    existing = _REGISTRY.get(adapter.key)
    if existing is not None and existing is not adapter:
        raise ValueError(f"Merchandise adapter key '{adapter.key}' is already registered.")
    _REGISTRY[adapter.key] = adapter
    return adapter


def get_adapter(key: str) -> MerchandiseAdapter:
    """Return the registered adapter for ``key``.

    Raises:
        ValidationFailed: If no adapter is registered under ``key``.
    """
    adapter = _REGISTRY.get(key)
    if adapter is None:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise ValidationFailed(f"Unknown merchandise adapter '{key}'. Registered: {known}.")
    return adapter


def available_adapters() -> dict[str, MerchandiseAdapter]:
    """Return a copy of the adapter registry keyed by adapter key."""
    return dict(_REGISTRY)

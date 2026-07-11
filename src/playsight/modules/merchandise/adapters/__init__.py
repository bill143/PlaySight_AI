"""Merchandise storefront adapters: protocol, registry, and stubs.

Importing this package registers the built-in adapter stubs (``shopify``,
``woocommerce``). Both raise ``NotImplementedError`` until Phase 2 lands the
real integrations.
"""

from playsight.modules.merchandise.adapters.base import (
    ExternalProduct,
    ExternalVariant,
    MerchandiseAdapter,
    available_adapters,
    get_adapter,
    register_adapter,
)
from playsight.modules.merchandise.adapters.shopify import ShopifyAdapter
from playsight.modules.merchandise.adapters.woocommerce import WooCommerceAdapter

__all__ = [
    "ExternalProduct",
    "ExternalVariant",
    "MerchandiseAdapter",
    "ShopifyAdapter",
    "WooCommerceAdapter",
    "available_adapters",
    "get_adapter",
    "register_adapter",
]

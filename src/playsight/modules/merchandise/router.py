"""Merchandise API router (prefix ``/shop``, feature flag ``merchandise``).

Mounted by the API layer under ``/api/v1``. All routes require authentication
(``get_tenant``) and the ``merchandise`` feature flag; writes additionally
require the ``admin`` or ``shop_manager`` role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from playsight.api.deps import get_tenant
from playsight.auth.rbac import Role, require_roles
from playsight.config.flags import require_feature
from playsight.db.session import get_db
from playsight.modules.merchandise import schemas
from playsight.modules.merchandise.models import Category, Product, ProductVariant
from playsight.modules.merchandise.service import MerchandiseService

router = APIRouter(
    prefix="/shop",
    tags=["shop"],
    dependencies=[Depends(get_tenant), Depends(require_feature("merchandise"))],
)

# Module-level singletons so route defaults contain no function calls (B008).
_require_shop_writer = require_roles(Role.ADMIN, Role.SHOP_MANAGER)
_require_shop_analytics = require_roles(Role.ADMIN, Role.SHOP_MANAGER, Role.FINANCE_ADMIN)


@router.get("/categories", response_model=list[schemas.CategoryRead])
def list_categories(
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Category]:
    """List the club's product categories."""
    return MerchandiseService(db).list_categories(tenant.club_id)


@router.post("/categories", response_model=schemas.CategoryRead, status_code=201)
def create_category(
    payload: schemas.CategoryCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> Category:
    """Create a product category."""
    return MerchandiseService(db).create_category(tenant.club_id, payload)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> None:
    """Delete a category (products keep existing, uncategorized)."""
    MerchandiseService(db).delete_category(tenant.club_id, category_id)


@router.get("/products", response_model=list[schemas.ProductRead])
def list_products(
    category_id: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> list[Product]:
    """List the club's products, optionally filtered by category/active flag."""
    return MerchandiseService(db).list_products(
        tenant.club_id, category_id=category_id, active_only=active_only
    )


@router.post("/products", response_model=schemas.ProductRead, status_code=201)
def create_product(
    payload: schemas.ProductCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> Product:
    """Create a product, optionally with initial variants."""
    return MerchandiseService(db).create_product(tenant.club_id, payload)


@router.get("/products/{product_id}", response_model=schemas.ProductRead)
def get_product(
    product_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
) -> Product:
    """Fetch one product with its variants."""
    return MerchandiseService(db).get_product(tenant.club_id, product_id)


@router.patch("/products/{product_id}", response_model=schemas.ProductRead)
def update_product(
    product_id: str,
    payload: schemas.ProductUpdate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> Product:
    """Apply a partial update to a product."""
    return MerchandiseService(db).update_product(tenant.club_id, product_id, payload)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> None:
    """Delete a product and its variants."""
    MerchandiseService(db).delete_product(tenant.club_id, product_id)


@router.post("/products/{product_id}/variants", response_model=schemas.VariantRead, status_code=201)
def add_variant(
    product_id: str,
    payload: schemas.VariantCreate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> ProductVariant:
    """Add a size/color variant (unique SKU per club) to a product."""
    return MerchandiseService(db).add_variant(tenant.club_id, product_id, payload)


@router.patch("/variants/{variant_id}", response_model=schemas.VariantRead)
def update_variant(
    variant_id: str,
    payload: schemas.VariantUpdate,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> ProductVariant:
    """Apply a partial update to a variant."""
    return MerchandiseService(db).update_variant(tenant.club_id, variant_id, payload)


@router.delete("/variants/{variant_id}", status_code=204)
def delete_variant(
    variant_id: str,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> None:
    """Delete a variant."""
    MerchandiseService(db).delete_variant(tenant.club_id, variant_id)


@router.post("/variants/{variant_id}/inventory", response_model=schemas.VariantRead)
def adjust_inventory(
    variant_id: str,
    payload: schemas.InventoryAdjust,
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_writer),
) -> ProductVariant:
    """Apply a signed inventory adjustment to a variant (result must be >= 0)."""
    return MerchandiseService(db).adjust_inventory(tenant.club_id, variant_id, payload.delta)


@router.get("/analytics/sales")
def sales_analytics(
    tenant: Any = Depends(get_tenant),
    db: Session = Depends(get_db),
    _user: Any = Depends(_require_shop_analytics),
) -> JSONResponse:
    """Basic sales analytics. Returns 501 until the commerce order tables land."""
    try:
        summary = MerchandiseService(db).sales_summary(tenant.club_id)
    except NotImplementedError:
        return JSONResponse(status_code=501, content={"todo": "phase2", "docs": "docs/ROADMAP.md"})
    return JSONResponse(content=summary)

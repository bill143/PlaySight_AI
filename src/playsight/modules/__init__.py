"""Phase 2/3 module scaffolds, feature-flagged (CONTRACTS.md sections 10, 12).

Each submodule follows the same layout: ``models.py`` (SQLAlchemy tables on the
shared ``playsight.db.base.Base`` metadata, club-scoped), ``schemas.py``
(pydantic v2), ``service.py`` (simple CRUD implemented, advanced flows stubbed
with ``NotImplementedError``), ``router.py`` (FastAPI router guarded by
``playsight.config.flags.require_feature``), and a ``README.md``.

Concurrent contributors own individual submodules and only share this
namespace, so the helpers below discover submodules dynamically and tolerate
scaffolds that do not exist yet.
"""

from __future__ import annotations

import importlib
from typing import Any

#: Module keys, matching feature-flag keys (CONTRACTS.md section 10).
MODULE_KEYS: tuple[str, ...] = (
    "competition",
    "merchandise",
    "playbook",
    "training",
    "nutrition",
    "registration",
    "payments",
    "commerce",
)


def import_all_models() -> list[str]:
    """Import every available module's ``models`` so tables register on metadata.

    Call this before ``Base.metadata.create_all`` (or Alembic autogenerate) to
    make the Phase 2/3 scaffold tables visible.

    Returns:
        The module keys whose models were imported. Scaffolds that do not
        exist yet are skipped silently so partial checkouts keep working.
    """
    loaded: list[str] = []
    for key in MODULE_KEYS:
        try:
            importlib.import_module(f"playsight.modules.{key}.models")
        except ModuleNotFoundError:
            continue
        loaded.append(key)
    return loaded


def iter_routers() -> list[Any]:
    """Return the ``router`` of every available module (for API wiring).

    Routers already carry their ``require_feature`` guard, so including all of
    them is safe: disabled modules answer HTTP 403 ``feature_disabled``.
    """
    routers: list[Any] = []
    for key in MODULE_KEYS:
        try:
            module = importlib.import_module(f"playsight.modules.{key}.router")
        except ModuleNotFoundError:
            continue
        router = getattr(module, "router", None)
        if router is not None:
            routers.append(router)
    return routers

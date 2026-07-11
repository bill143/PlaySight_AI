"""FastAPI REST API (CONTRACTS.md sections 4, 6, 10, 12).

Layout:

- ``main.py`` -- app factory ``create_app()`` and module-level ``app``.
- ``deps.py`` -- shared dependencies (db, current user, tenant, pagination).
- ``middleware.py`` -- correlation-id middleware.
- ``routers/`` -- one module per resource, all mounted under ``/api/v1``.
- ``schemas/`` -- pydantic v2 request/response models.
"""

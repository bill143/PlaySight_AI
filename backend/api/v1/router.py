"""API v1 router aggregating all endpoint routers."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1 import artifacts, auth, health, highlights, jobs, matches, players, publishing, reports

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(matches.router)
api_router.include_router(jobs.router)
api_router.include_router(players.router)
api_router.include_router(reports.router)
api_router.include_router(highlights.router)
api_router.include_router(artifacts.router)
api_router.include_router(publishing.router)

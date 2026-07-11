# PlaySight AI Roadmap

## Status legend

- 🚧 In Progress — active MVP delivery scope
- 📋 Planned — future milestone not yet in active delivery
- ✅ Done — completed milestone

## Milestone summary

| Milestone | Status |
| --- | --- |
| M1 Detection & Tracking (Phase 1) | 🚧 In Progress |
| M2 Identification (Phase 1) | 🚧 In Progress |
| M3 Analytics & Reporting (Phase 1) | 🚧 In Progress |
| M4 Highlights, Export & Publishing (Phase 1) | 🚧 In Progress |
| M5 Tactical Insights (Phase 1 - future) | 📋 Planned |
| M6 Competition Integration (Phase 2) | 📋 Planned |
| M7 Playbook + Training (Phase 2) | 📋 Planned |
| M8 Nutrition + Merchandise (Phase 2) | 📋 Planned |
| M9 Advanced Tactical Assistant (Phase 3) | 📋 Planned |
| M10 Registration & Membership (Phase 3) | 📋 Planned |

## M1 Detection & Tracking (Phase 1)

Status: 🚧 In Progress

This milestone establishes the frame-by-frame computer vision foundation required for every downstream feature in the platform. It focuses on robust entity localization, stable track continuity, and reusable metadata for analytics and reporting.

Deliverables:

- YOLO-based player/ball detection
- ByteTrack-based multi-object tracking
- Persistent track IDs

## M2 Identification (Phase 1)

Status: 🚧 In Progress

This milestone turns anonymous tracks into known player identities. It combines jersey OCR, appearance-based Re-ID signals, and entity resolution logic so downstream reports can map observations back to canonical roster records.

Deliverables:

- Jersey number OCR
- Re-ID embeddings
- Identity resolution pipeline mapping tracks to canonical Player records

## M3 Analytics & Reporting (Phase 1)

Status: 🚧 In Progress

This milestone converts processed trajectories and events into analyst-facing output. It emphasizes per-player insight generation, match-level summaries, and machine-readable artifacts for internal and external consumers.

Deliverables:

- Per-player statistics (distance, speed, possessions, passes, shots)
- Event detection/segmentation
- Heatmaps
- Match summary generation
- PDF/JSON player & match reports

## M4 Highlights, Export & Publishing (Phase 1)

Status: 🚧 In Progress

This milestone packages the core pipeline into deliverable media and distribution workflows. It covers clip extraction, export formats, audio summaries, and publishing hooks so generated insights can be shared outside the application.

Deliverables:

- Automated highlight clip extraction & merging
- Annotated video export
- Audio match summaries
- CSV/JSON/Parquet data export
- YouTube publishing integration

## M5 Tactical Insights (Phase 1 - future)

Status: 📋 Planned

This milestone expands the analytics layer into richer tactical interpretation. It lays the groundwork for advanced team-shape and possession analysis that can power coaching workflows and future AI-assisted recommendations.

Deliverables:

- Formation detection
- Pressing intensity
- Possession chains
- Foundational work for advanced tactics

## M6 Competition Integration (Phase 2)

Status: 📋 Planned

This milestone connects the platform to structured league and competition data sources. It enables synchronization of schedules, standings, and external metadata into the application and backend services.

Deliverables:

- League/competition data feeds
- Standings
- Fixture syncing (`backend/competition/`)

## M7 Playbook + Training (Phase 2)

Status: 📋 Planned

This milestone brings team preparation and coaching workflows into the product. It covers tactical content authoring and training management features that can integrate with analytics produced by earlier milestones.

Deliverables:

- Tactical playbook authoring tools
- Training plan management (`backend/playbook/`, `backend/training/`)

## M8 Nutrition + Merchandise (Phase 2)

Status: 📋 Planned

This milestone broadens the platform into adjacent club operations. It adds wellness-adjacent tracking and commerce integration features that can support a wider sports organization workflow.

Deliverables:

- Player nutrition tracking
- Merchandise store integration (`backend/nutrition/`, `backend/merchandise/`)

## M9 Advanced Tactical Assistant (Phase 3)

Status: 📋 Planned

This milestone introduces higher-level AI assistance built on tactical, reporting, and training data. The goal is to support coaches and analysts with explainable recommendations, scenario exploration, and decision support.

Deliverables:

- AI-assisted tactical recommendations building on M5/M7 data

## M10 Registration & Membership (Phase 3)

Status: 📋 Planned

This milestone extends the system into club administration and monetization workflows. It focuses on member onboarding, subscription structures, and payment-linked account management.

Deliverables:

- Club/member registration
- Membership tiers
- Payments (`backend/registration/`)

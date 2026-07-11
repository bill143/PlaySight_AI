# Contributing to PlaySight_AI

Thanks for helping build PlaySight_AI. This document covers local setup, the
quality gates every change must pass, and the one rule that governs all of it.

## The contract-first rule

**[`docs/CONTRACTS.md`](docs/CONTRACTS.md) is the single source of truth** for
repository layout, dependencies, naming, database schema, module interfaces,
API shape, artifact filenames, feature flags, and coding standards.

- Implement **exactly** against it. Where it is silent, make sensible,
  production-quality choices consistent with it.
- If a contract must change, **change `docs/CONTRACTS.md` first**, then change
  the code. A PR that silently diverges from the contract will be rejected.
- Multiple contributors (human and agent) work on the codebase concurrently;
  the contract is what keeps independently written modules compatible.

## Local setup

Requirements: Python 3.11+ (3.11 and 3.12 are tested in CI), Node 20+ for the
dashboard, and `ffmpeg` on your `PATH` (the `imageio-ffmpeg` dependency can
resolve a binary, but a system ffmpeg is preferred).

```bash
# Python package (editable, with dev tooling)
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# Optional: real CV engines (heavy; NOT installed in CI)
pip install -e ".[cv]"

# Dashboard
cd dashboard && npm install
```

Everything runs without Docker by default: SQLite database, local object
storage under `./outputs/storage`, and eager in-process jobs whenever redis is
unreachable. Copy `.env.example` to `.env` to override settings.

Sanity check:

```bash
playsight init-db
playsight seed-demo
playsight process data/demo/demo_match.mp4
```

## Quality gates

CI runs these on every PR (see `.github/workflows/ci.yml`); run them locally
before pushing — a change is not done until all of them pass:

```bash
ruff check src tests          # lint (rules: E, F, I, UP, B, SIM; line length 100)
black --check src tests      # formatting (line length 100)
mypy src/playsight           # type check (non-strict, must be clean)
pytest -m "not cv"          # tests without the heavy [cv] extra

# Dashboard
cd dashboard
npm run lint
npm run build
```

`make lint`, `make fmt`, `make typecheck`, and `make test` wrap the same
commands if you have GNU make.

### Test rules

- Tests live in `tests/` (`unit/` + `integration/`) and must **not** require
  network access, a GPU, Docker, or the `[cv]` extra.
- Tests that genuinely need the `[cv]` extra are marked `@pytest.mark.cv` and
  are skipped in CI via `-m "not cv"`.
- Aim for >70% coverage on non-CV code paths.

## Coding standards (summary — CONTRACTS.md §19 is authoritative)

- Ruff + Black at 100 columns; mypy clean on `src/playsight`.
- `structlog` only in library code — **no `print()`** (the Typer CLI may use
  `rich`).
- Type hints everywhere; docstrings on public functions.
- Comments only for non-obvious constraints. Deferred work is written as
  `# TODO(phase2): ...` / `# TODO(phase3): ...` and must also appear in
  [`docs/ROADMAP.md`](docs/ROADMAP.md).
- Heavy CV dependencies (`torch`, `ultralytics`, `easyocr`, `supervision`) are
  imported lazily inside functions and always have deterministic stub
  fallbacks that mark their output with `"engine": "stub"`.
- Every core API query filters by `club_id` (tenancy); cross-club access
  answers 404, never 403.

## Submitting changes

1. Branch from `main`; keep changes scoped to one concern.
2. Update or add tests alongside the change.
3. If your change touches behavior described in `README.md`,
   `docs/ARCHITECTURE.md`, or `docs/API.md`, update the docs in the same PR.
4. Make sure all quality gates above pass, then open a PR with a short
   description of *what* changed and *why*.

## Legal & safety invariants (never regress these)

- No biometric face recognition anywhere; identification is jersey OCR +
  appearance embeddings, documented as confidence-scored estimation.
- YouTube publishing always requires explicit `confirm_rights: true` and
  defaults to `private` privacy.
- Passwords are bcrypt-hashed; storage keys never contain PII; sensitive
  mutations are audit-logged.
- Nutrition outputs carry a "not medical advice" disclaimer.

## Code of conduct

All participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
(Contributor Covenant 2.1).

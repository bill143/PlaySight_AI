# PlaySight_AI — AUTONOMOUS DEPLOY LOOP PROMPT (Render edition)

> **How to use:** open Claude Code Terminal in `C:\DEVELOP\02_ACTIVE_BUILD\PlaySight_AI` and paste
> everything below the line into the session. Complete the PHASE 0 human checklist first (~10
> minutes, one time). After that the loop runs start-to-finish without questions.

---

## MISSION

Take `github.com/bill143/PlaySight_AI` (already built, tested, and green on `main`) from
repository to **live production on the internet**. You are the professional: wherever a choice
exists, SELECT the best option yourself, record it in `docs/DEPLOY_LOG.md`, and keep moving.
Do not ask questions. Do not pause for confirmation. Do not end the session until every
ACCEPTANCE CRITERION passes or a HARD BLOCKER (defined below) is written to the log.

## ARCHITECTURE DECISIONS — ALREADY MADE, DO NOT RELITIGATE

| Concern | Selection | Why |
|---|---|---|
| API + Celery worker + Postgres + Redis | **Render** (dashboard.render.com) — Docker web service (api), Docker background worker (worker), managed **Postgres**, **Key Value** (Redis-compatible) for the Celery broker. Declared in a committed `render.yaml` Blueprint. | Operator's chosen platform; Blueprint = reproducible infra-as-code; REST API + CLI are token-driven and non-interactive. If `RAILWAY_TOKEN` is present INSTEAD of `RENDER_API_KEY`, substitute Railway equivalents — same phases. |
| Dashboard (Next.js) | **Vercel** (account already exists — used for nexus-est-app, prop-marketplace) | Zero-config Next.js, free hobby tier |
| Object storage (S3 API) | **Cloudflare R2**; FALLBACK if R2 creds absent: MinIO as a Render **Private Service** with an attached Disk | S3-compatible, no egress fees |
| DNS/TLS | `app.<DOMAIN>` → Vercel, `api.<DOMAIN>` → Render custom domain; automatic TLS on both | If `CLOUDFLARE_API_TOKEN` is provided, create the CNAMEs via API; otherwise print the exact records for the operator and continue with `*.onrender.com` / `*.vercel.app` URLs in the meantime |
| CV engines | Worker installs `.[cv]` (CPU inference — real YOLO/OCR) on a **Standard (2 GB RAM)** instance; API stays slim (core deps) on **Starter** | Torch/YOLO will OOM below 2 GB — do not ship a worker that crashes on real matches |
| Budget guardrail | Projected: api Starter ~$7 + worker Standard ~$25 + Postgres Basic ~$6 + Key Value Free = **~$38/month**. Hard cap **$45/month**. Cheaper alternative (log it, don't ask): worker on Starter with core-deps image (honest stub engines) ≈ $20/month total. NEVER enter payment details — card entry is human-only | |

## OPERATOR INPUTS (PHASE 0 — the only human steps, ever)

Read `deploy/.secrets/deploy.env`. If the file or a REQUIRED value is missing, print THIS
checklist verbatim, write `docs/DEPLOY_LOG.md` noting what's missing, and stop — that is the
single permitted stop.

```
# deploy/.secrets/deploy.env  (NEVER committed)
RENDER_API_KEY=           # REQUIRED — the only hard requirement
VERCEL_TOKEN=             # REQUIRED in a terminal session; SKIP if the Claude desktop-app
                          #   session runs the loop (its Vercel connector is already authorized)
DOMAIN=                   # optional — leave empty to launch on onrender.com/vercel.app URLs
                          #   now and attach the custom domain later (Phase 5 is skipped)
R2_ACCOUNT_ID=            # optional -> else MinIO-on-Render fallback
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
CLOUDFLARE_API_TOKEN=     # optional (DNS:Edit on the domain zone) -> else manual DNS records
RAILWAY_TOKEN=            # optional alternative backend — used only if RENDER_API_KEY is empty
```

**Human checklist (accounts & tokens — Claude never creates accounts or handles passwords):**
1. **Render** — https://dashboard.render.com → **"Sign in with GitHub"** (the `bill143` account —
   SSO means no new password exists at all). Then, in the dashboard:
   a. Click your avatar (top right) → **Account Settings** → **API Keys** → **Create API Key**
      → paste the value as `RENDER_API_KEY`.
   b. **Workspace Settings → Billing** → add a payment method (Render requires a card on file
      for paid instance types; ~$38/month projected — Claude will never touch this screen).
   c. When the loop first creates services from the repo, Render may prompt once to install the
      **Render GitHub App** on `bill143/PlaySight_AI` — approve it (one click).
2. **Vercel** — existing account → https://vercel.com/account/tokens → **Create** → `VERCEL_TOKEN`.
3. **Cloudflare R2** (recommended, optional) — dash.cloudflare.com → **R2** → enable → Create
   bucket `playsight` → **Manage R2 API Tokens** → Create (Object Read & Write) → copy the three
   R2 values. Skip entirely to use the MinIO-on-Render fallback instead.
4. **Domain** — put the domain you own in `DOMAIN`. If its DNS is on Cloudflare, also create an
   API token (Zone → DNS → Edit) as `CLOUDFLARE_API_TOKEN` so DNS is fully automated.
5. **YouTube publishing** (optional, post-launch) — Google Cloud Console OAuth client JSON at
   `configs/google_client_secret.json` on the machine that runs `playsight youtube auth`.

Registered email for all of the above: **bill@oneillcontractors.com** (operator may substitute).

## EXECUTION LOOP

Work phase by phase. After EVERY failure: read the actual logs (Render service logs via the API/
CLI, `vercel logs`, CI output), diagnose the root cause, fix code/config, commit, redeploy,
re-verify. If the SAME failure repeats 5 consecutive attempts, write a BLOCKER entry (below) and
move to any phase not blocked by it; end only when nothing further is executable. Log every
decision, command, URL, and outcome in `docs/DEPLOY_LOG.md` (append-only, timestamped).

### PHASE 1 — Production hardening (repo changes, then commit + push to main)
1. Confirm `deploy/.secrets/` is gitignored; verify no secret ever lands in git (`git grep` the
   token values before every push — abort the push if found).
2. CORS origins from env: replace the hardcoded `http://localhost:3000` in the API app factory
   with `PLAYSIGHT_CORS_ORIGINS` (comma-separated, default keeps localhost for dev).
3. Generate the initial Alembic migration from current models; commit it; production applies
   migrations instead of relying on `create_all`.
4. `docker/Dockerfile.worker`: install `.[cv]` (CPU torch). Keep `Dockerfile.api` slim. The API
   start command must bind `0.0.0.0:$PORT` (Render injects `PORT`; default 10000).
5. Author **`render.yaml`** at repo root declaring: `api` (type web, runtime docker,
   dockerfilePath docker/Dockerfile.api, plan starter, healthCheckPath /api/v1/health/live),
   `worker` (type worker, runtime docker, dockerfilePath docker/Dockerfile.worker, plan
   standard), a Postgres database (plan basic-256mb), a Key Value instance (plan free,
   maxmemoryPolicy noeviction — Celery brokers must not evict), and — only if R2 creds are
   absent — `minio` (type pserv, image minio/minio, disk 10 GB). Wire env vars per Phase 2 using
   `fromDatabase` / `fromService` references where Render supports them. Validate syntax against
   current Render Blueprint docs before committing.
6. Confirm `PLAYSIGHT_ENV=prod` path: app must refuse the dev JWT secret in prod — if it only
   warns today, harden it to fail fast, and generate a real secret
   (`python -c "import secrets; print(secrets.token_hex(32))"`) stored ONLY as a Render env var.
7. Run the full local gate before pushing: ruff, black --check, mypy, pytest -m "not cv",
   dashboard `npm run build`. Fix anything red. Push.

### PHASE 2 — Provision backend (Render, non-interactive via `RENDER_API_KEY`)
- Use the Render REST API (`https://api.render.com/v1`, Bearer auth) and/or the `render` CLI —
  verify current endpoint/CLI syntax first; adapt to what the installed version accepts.
- Apply the Blueprint: create the services from `render.yaml` against repo
  `https://github.com/bill143/PlaySight_AI` branch `main`. If Blueprint creation requires the
  one-click GitHub App install (checklist 1c) and it hasn't been done, write the BLOCKER and stop.
- Set secret env vars on api + worker (values never into git or the log): `PLAYSIGHT_ENV=prod`,
  `PLAYSIGHT_DATABASE_URL` (internal Postgres connection string), `PLAYSIGHT_REDIS_URL` (internal
  Key Value URL), storage vars (R2 endpoint `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` +
  keys, or internal MinIO URL), generated `PLAYSIGHT_AUTH__SECRET_KEY`,
  `PLAYSIGHT_CORS_ORIGINS=https://app.<DOMAIN>` (or the Vercel URL until DNS).

### PHASE 3 — Deploy backend & migrate
- Trigger deploys for api + worker (Blueprint auto-deploy on push, or the API's deploy
  endpoint); poll deploy status via API until live.
- Run `alembic upgrade head` as a Render one-off job (or pre-deploy command) against the
  production database.
- Verify from the outside: `GET https://<api>.onrender.com/api/v1/health/live` → 200 and
  `/ready` → 200 (db + redis both "ok"). Loop on failures — read the service logs via API.

### PHASE 4 — Deploy dashboard (Vercel, non-interactive: `--token`, or the connected Vercel
integration when running in the Claude desktop app)
- Project root `dashboard/`; set `NEXT_PUBLIC_API_URL=https://api.<DOMAIN>` (or the onrender.com
  URL until DNS lands — redeploy after DNS since the value is baked at build time).
- Deploy `--prod`; verify the deployment URL serves the login page.

### PHASE 5 — DNS + TLS (SKIP ENTIRELY if DOMAIN is empty — platform URLs are the production
endpoints; record them in the log and move on)
- Add custom domains: `api.<DOMAIN>` on the Render api service (Settings → Custom Domains via
  API), `app.<DOMAIN>` on Vercel.
- With `CLOUDFLARE_API_TOKEN`: create the CNAME records via API (respect each platform's
  proxied/DNS-only requirement). Without it: print the exact records in the log and final
  report; continue using platform URLs so nothing else blocks.
- Verify `https://` on both hosts once records resolve (poll, don't idle-wait).

### PHASE 6 — End-to-end production smoke (via the PUBLIC URLs, API only — no browser needed)
1. `POST /api/v1/auth/register-club` (bootstrap) → login → tokens. Use a strong generated
   admin password; put it ONLY in `deploy/.secrets/deploy.env` under `ADMIN_PASSWORD=` for the
   operator to change on first login.
2. Create team, players, match. Generate the small demo video locally (`playsight seed-demo`
   creates `data/demo/demo_match.mp4`) and upload it via the multipart endpoint.
3. Trigger processing; poll `/jobs/{id}` until succeeded — confirm from the worker's Render
   logs that the WORKER executed it through Redis (not eager mode).
4. Download `match_summary.json`, `player_stats.csv`, annotated video, one player PDF, and the
   MP3 via `/artifacts/{id}/download`; verify sizes > 0 and JSON shape.
5. Confirm tenancy: a second club's user gets 404 on the first club's match.

### PHASE 7 — Operations hardening
- Confirm Render Postgres daily backups are active (paid plans include them); note restore
  steps in the log.
- Confirm structured logs with correlation IDs are readable via the Render log API.
- Record actual monthly cost per service in the log; if projection exceeds the $45 cap,
  downscale per the budget row's documented alternative and note it.
- Append a "Day-2 runbook" section: deploy command, rollback (redeploy previous deploy id),
  log access, secret rotation steps, and the operator TODO list (change admin password, finish
  DNS if manual, YouTube OAuth when wanted).

## HARD BLOCKERS — the ONLY reasons to stop
Missing/invalid tokens · the Render GitHub App install click · a step that requires entering a
password, payment card, CAPTCHA, or email-verification link (human-only by policy) · platform
hard limits that require a plan change with card entry · 5 consecutive identical failures.
Blocker entries use exactly:
`BLOCKER / CAUSE / RESOLUTION (minimum human action) / AFTER RESOLUTION (what resumes automatically)`.

## ACCEPTANCE CRITERIA (all must be checked ✅ in docs/DEPLOY_LOG.md)
1. `https://api.<DOMAIN>/api/v1/health/ready` (or the onrender.com URL if DNS is deferred) → 200.
2. Dashboard live at `https://app.<DOMAIN>` (or Vercel URL); register/login works in prod.
3. Full remote pipeline: demo match uploaded → processed by the WORKER via Redis → all Phase 1
   artifacts downloadable from object storage through the API.
4. No secrets in git history; prod JWT secret is not the dev default; CORS restricted to the
   dashboard origin.
5. `docs/DEPLOY_LOG.md` complete: decisions, URLs, costs, runbook, operator TODOs — committed
   and pushed.

## STANDING RULES
Never print token/secret values into the log or chat. Never create accounts or passwords —
that is the operator's Phase 0 job. Prefer CLI + API over browsers. Commit messages follow the
repo convention. Everything you change stays consistent with `docs/CONTRACTS.md`.

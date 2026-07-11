# PlaySight Dashboard

Next.js 14 (App Router) + TypeScript (strict) + Tailwind dashboard for PlaySight_AI.
Implements `docs/CONTRACTS.md` section 15.

## Development

```bash
npm install
npm run dev        # http://localhost:3000
```

The API base URL comes from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`);
see `.env.local.example`. JWTs are stored in `localStorage` under `ps_access` /
`ps_refresh`, with transparent refresh-on-401 handled by `lib/api.ts`.

## Scripts

- `npm run dev` — dev server
- `npm run build` — production build (strict TS + ESLint)
- `npm run start` — serve the production build
- `npm run lint` — ESLint (`next/core-web-vitals`)

## Pages

- `/login`, `/register` — auth (register bootstraps the first club)
- `/` — matches list, create match, upload video, trigger processing
- `/matches/[id]` — Timeline / Players / Reports / Highlights / Export & Publish tabs

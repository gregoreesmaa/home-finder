# AGENTS.md — home-finder collaboration contract

> Stack: Next.js + MapLibre + deck.gl + FastAPI scoring + PostGIS. Goal: ranked list
> sorting best-to-worst on BOTH metrics (livability fit + price fairness/steal)
> plus region goodness/badness heatmap on a real map.

## 1. Pipeline: ideas → tasks → work → PRs → review → merged, pushed

1. **Ideas** — open a GitHub issue per idea (feature, portal adapter, bug).
   Label: `idea`, `feature`, `portal`, or `bug`.
2. **Tasks** — maintainers convert accepted ideas into actionable tasks:
   issue gets acceptance criteria + DoD checklist (see §2).
3. **Work** — each builder works in a distinct git worktree + branch:
   `.worktrees/<issue>-<slug>` (see §3). One issue per worktree/PR.
   The initial scaffold on `main` is the only exception (no parallel writers).
4. **PRs** — push branch, open PR referencing `Closes #<n>`.
   PR description must contain the DoD evidence (what you ran, test output).
5. **Review** — a fresh no-context reviewer reviews each PR: approve/merge
   or request changes (loop until approved). Reviewer checks DoD evidence,
   runs tests, and verifies no regressions.
6. **Merged, pushed** — squash-merge on approval; delete worktree after merge;
   `main` must stay green and pushed to origin.

## 2. Definition of Done (DoD) — every task

A task is DONE only when it **proves it works + has regression tests**:

- [ ] Feature/fix implemented per acceptance criteria (ranked-list sorting,
      heatmap layer, portal adapter, etc.).
- [ ] Proof it works: commands run + observed output pasted in PR
      (e.g. `pytest`, `npm test`, `curl` against scoring API, screenshot for map).
- [ ] Regression tests added covering the new behavior and re-run green.
- [ ] Existing relevant test suite run green (no regressions).
- [ ] PR reviewed by a fresh no-context reviewer → approved + merged.

No proof + no tests = not done.

## 3. Worktree convention

```bash
git worktree add .worktrees/<issue>-<slug> -b <issue>-<slug>
# e.g. git worktree add .worktrees/12-kv-ee-adapter -b 12-kv-ee-adapter
# work there, commit, push, open PR, get fresh review, merge, then:
git worktree remove .worktrees/<issue>-<slug>
```

- `.worktrees/` is git-ignored scratch space (never committed).
- Branch name == worktree directory name == `<issue>-<slug>`.
- One builder per worktree; never two agents on the same worktree/branch.

## 4. Backlog seed (to become issues)

1. Ranked-list sorting (livability fit + price fairness/steal, best-to-worst).
2. Heatmap layer (region goodness/badness on real MapLibre map).
3. Estonian listing portals: one issue + one adapter per portal
   (kv.ee, city24.ee, kinnisvara24.ee, kinnisvaraweb.ee, okidoki.ee, osta.ee,
   Facebook Marketplace/groups, domus.ee, uusmaa.ee, pindi.ee, 1partner.ee,
   oberhaus.ee, arcovara.ee, lvm.ee, remax.ee).
4. Scoring API (FastAPI) + PostGIS schema backing 1–3.

## 5. Repo hygiene

- `main` is protected: changes only via reviewed PRs (scaffold on `main`
  was the one-time bootstrap exception).
- Public repo: no secrets, no personal data, no scraped listing dumps.
- Adapters poll politely (rate-limited, ideally daily cron); never commit
  scraped data — fixtures only.

## 6. Commands

```bash
# web (Next.js + MapLibre + deck.gl)
npm install
npx turbo run test          # or: npm test --workspace @home-finder/web
npm run dev --workspace @home-finder/web

# QA gates (also enforced by .github/workflows/ci.yml on every PR)
npm run lint                # eslint, repo-wide
npm run typecheck           # tsc --noEmit (web)
npm test                    # turbo: vitest unit suites
npm run test:python         # pytest scoring suite, from repo root
npm run test:e2e --workspace @home-finder/web   # playwright smoke (needs: npx playwright install chromium)

# scoring (FastAPI)
pip install -r services/scoring/requirements.txt
python3 -m pytest services/scoring/tests -q
uvicorn app:app --reload --app-dir services/scoring
DATABASE_URL=postgresql://homefinder:homefinder@localhost:5432/homefinder \
  python3 services/scoring/ingest.py --cache-dir /tmp/hf-cache   # live import (polite, page 1/portal)

# everything (PostGIS + API + web)
docker compose up --build
```

Scaffold DoD evidence (v0.1, on `main`): `vitest` 2 files green,
`pytest` 2 files green — see commit message.

## 7. Operating mindset (for agents)

Distilled from what actually worked shipping v1. Prefer these over cleverness:

1. **Evidence before claims.** Reproduce against real code and live state;
   never trust summaries — including prior session summaries. Read the file,
   run the command, quote the output. A confident patch you never saw pass
   the repo's tests is the most common wrong answer.
2. **Honest systems over fake precision.** Fallbacks must be explicit and
   honestly labeled (never present fallback/demo as live). Transport errors
   are never cached as data; never invent sources, reviews, or scores.
3. **Verify at the layer the user sees.** Screenshots for UI, DB tallies for
   data, real cron runs for pipelines — not just unit greens. A green suite
   with broken UX is not done.
4. **Polite automation.** Pace, backoff, mirrors, caches; treat HTTP 429 as
   a stop signal, not a retry dare. Cold caches plus retries pile on — bulk
   work should converge over runs, not hammer through in one.
5. **Make gray areas reviewable.** Document judgment calls in code comments
   and PR reviewer notes; flag ambiguity instead of hiding it. The reviewer
   can only catch what you surface.
6. **Hermetic tests by default.** Guard the suite against network access;
   cover live paths with explicitly-flagged integration tests, not unit runs.
7. **Small diffs, one issue per worktree/PR**, DoD evidence pasted in the PR.

## 8. Agent UX loop (the standing user-driven QA task, #80)

`node scripts/agent-ux-loop.mjs [--base URL] [--api URL] [--out DIR]`
drives the running site like a buyer (sorts, weights, POI, map pan,
filters), collects every console/page error, and writes screenshots +
`report.json`. Zero page errors is the bar; fix issues and re-run the
loop until all green, then report the loop output as DoD evidence.

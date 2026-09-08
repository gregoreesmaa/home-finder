# AGENTS.md — home-finder collaboration contract (draft skeleton)

> Stack: Next.js + MapLibre + FastAPI scoring + PostGIS. Goal: ranked list
> sorting best-to-worst on BOTH metrics (livability fit + price fairness/steal)
> plus region goodness/badness heatmap on a real map.

## 1. Pipeline: ideas → tasks → work → PRs → review → merged, pushed

1. **Ideas** — open a GitHub issue per idea (feature, portal adapter, bug).
   Label: `idea`, `feature`, `portal`, or `bug`.
2. **Tasks** — maintainers convert accepted ideas into actionable tasks:
   issue gets acceptance criteria + DoD checklist (see §2).
3. **Work** — each builder works in a distinct git worktree + branch:
   `.worktrees/<issue>-<slug>` (see §3). One issue per worktree/PR.
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
   (e.g. kv.ee, city24/realestate, kinnisvara24, okidoki/facebook — verify list).
4. Scoring API (FastAPI) + PostGIS schema backing 1–3.

## 5. Repo hygiene

- `main` is protected: changes only via reviewed PRs.
- Public repo: no secrets, no personal data, no scraped listing dumps.

# Overturn hunt log — G6 muinas-register designations p158/272/320/351/354/355/359/360 (issue #237)

> Time-boxed source hunt for Group 6 (parameters3.md §5.6).
> Hunted 2026-09-13 (~15 min). **Verdict: KEEP the NULLs (dated
> negative)** — the moved register answers HTTP 520 and the
> documented hostname is NXDOMAIN, so no designation dump exists
> to join per building. The test-pinned verdict dims live in
> `services/scoring/dims_overturn_muinas.py`, pinned by
> `services/scoring/tests/test_dims_overturn_muinas.py`.
> Re-probe the register no later than **2026-12-13** (quarterly).

## Verdict

**No pollable designation dump — all eight stay NULL with
Estonian register reasons.** A designation is a per-building
decree: even with a dump, the honest output is a per-building
designation join + procedure dims, never a gradient (a decree is
not a field — nomap.md §3 G6). Painting mapped-heritage density
as eight per-building facts would re-skin p72 under new names
(OTA PR #131 precedent).

What flipped vs stayed NULL: **nothing flipped today** (no dump
to join). When the register answers, p158/p320/p355/p360 can
graduate to per-building procedure/designation dims fed ONLY by
the pinned `lookup_muinas` join; p272/p351/p354/p359 stay NULL
permanently — their questions need a different record (kataster
easement, window survey, geotechnical survey, lab result) that no
designation dump holds. `DESIGNATION_GRADUABLE` /
`DESIGNATION_NEVER` in the module pin this split.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

2 single GETs + 2 DNS lookups total (labelled one-off user-agent
`home-finder muinas overturn #237 (one-off, single GETs, no
retry; contact via GitHub home-finder)`, paced ≥ 20 s,
`--max-time 25`, headers + visible-text scope read only). Raw
bodies: `/tmp/hf-muinas-237/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://register.muinas.ee/` → HTTP 520, 16 B (`error code: 520`) | repeated ~22 s later, same 520 | moved register's origin is down — a 520ing page cannot be polled, let alone joined |
| `nslookup register.muinas.ee` → resolves (proxy answers) | DNS alive, origin down | transport error, never data |
| `nslookup register.muinsuskaitseamet.ee` → NXDOMAIN | parameters3 Group 6 documented hostname still dead | no machine path on the documented host either |

Judgment call: the check stopped at entry level on purpose — no
WFS layer crawl, no app-API chasing, no Maa-amet `mka:*` mirror
crawl (that mirror stays a reopening lead, same line as
docs/p4_muinsus.md). Deeper harvesting is exactly the scraping
this repo refuses (AGENTS.md §5).

## Near-miss proxies considered and refused

- **Mapped-heritage density as designation** (`heritage=*`
  nearness): density predicts review likelihood (already owned by
  dims_group06 p72/p320 + dims_group06b p355 heuristics), never a
  per-building decree — refused.
- **Designation as easement/survey/lab** (p272/p351/p354/p359):
  a decree states protection, never a parcel contract, a window
  survey, soil mechanics, or a lab result — refused permanently.
- **Maa-amet `mka:*` mirror as silent substitution**: unprobed
  here; a pollable mirror reopens the issue, it does not join
  silently.

## What stays open (overturn path, not wired here)

1. Re-probe `register.muinas.ee` quarterly (TTL: quarterly);
   paste fresh evidence in the reopen PR.
2. If the register serves a pollable designation feed
   (WFS/REST/CSV) or the Maa-amet `mka:ehitis`/`mka:kaitsevoond`
   mirror proves pollable, transcribe one Tallinn week of dated
   rows and run them through `parse_muinas_row` +
   `build_muinas_index` + `lookup_muinas` on fixtures first.
3. Graduate ONLY the `DESIGNATION_GRADUABLE` dims from joined
   records (per-building procedure/designation, never 0/100
   gradients); keep NULL-with-Estonian-reason for every miss.
   Shared/group files (`dims_group06*.py`,
   `dims_p4_muinsus.py`, `livability.py`, WEIGHTS, `docs/nomap.md`)
   are deliberately untouched here — the final docs-index PR
   updates nomap.md.

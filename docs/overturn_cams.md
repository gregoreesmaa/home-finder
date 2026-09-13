# Overturn hunt log — G7 air/radon/contamination proxies [CAMS/EGT/KIK] (issue #238)

> Time-boxed source hunt for Group 7 no-map set p66/p67/p137, p204/p252,
> p448/p471/p499 (parameters3.md §5.7; p260/p316/p401/p402 already score
> as proxy dims in `dims_group07c.py` and are out of scope).
> Hunted 2026-09-13 (~40 min: web search + 9 polite requests). **Verdict:
> KEEP the NULLs live** — no open machine-readable feed for any of the
> three legs. The test-pinned verdict dims live in
> `services/scoring/dims_overturn_cams.py`, pinned by
> `services/scoring/tests/test_dims_overturn_cams.py`.
> Re-check the four discovery surfaces no later than **2027-03-13**.

## Verdict

**No open feed — nothing flips live.** Copernicus CAMS needs a free ADS
account + personal token (no account is created per the issue RULE, so
the dated negative keeps the verdict for that leg); the EGT radon-risk
map exists only as static human documents (ministry PDF + 9-sheet
1:500 000 set + JRC 10 km viewer grid with gated bulk); the KIK
residual-pollution DB has no politely discoverable open surface; and
the parameters3-documented Õhuseire machine endpoint 404s on the live
host. What the PR ships instead is honest plumbing with no live data:
a key-gated CAMS fetcher (no ticket → `ValueError`, never a guessed
request), a fixture-proven coarse radon-class grid scorer (p66) and a
fixture-proven confirmed-site proximity scorer (p204, bands mirroring
`dims_group07b.dim_brownsoil`), plus six pure-NULL legs — all scoring `None` without
a cached extract. Shared/group files (`dims_group07*.py`,
`livability.py`, WEIGHTS, `docs/nomap.md`) are deliberately untouched;
the final docs-index PR updates nomap.md.

| Param | Question | Verdict | Why |
|---|---|---|---|
| p66 radon gas levels | regional radon class | NULL live; grid shape ready | EGT map is PDF sheets, JRC bulk gated — no machine class feed |
| p204 hazardous materials | confirmed-site proximity | NULL live; KIK shape ready | no open KIK/Seveso bulk; bands mirror p189 on reopen |
| p67 pests/wildlife | surveillance | NULL | no surveillance feed at any checked surface |
| p137 seasonal allergens | pollen normals | NULL | aerobiological results are human pages; parks emit pollen |
| p252 invasive plants | species surveillance | NULL | no species feed; mapped green is native/planted |
| p448 harvest dust/traffic | season timing | NULL | no timing feed; p409-footprint reuse would duplicate p409 |
| p471 lead service lines | pipe material | NULL | 0,13% age coverage, zero pipe tags — age proxy is noise |
| p499 radon aesthetic | facade judgment | NULL always | no data possible in principle; on-site facade check |

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

9 tiny requests total (single GETs/HEADs, labelled one-off user-agent
`home-finder-238-hunt/1.0 (one-off open-data check; contact via GitHub
issue #238)`, paced ≥ 4 s, short timeouts, headers + visible-text
keyword scope read only, no form submissions, no XHR probing, no blind
deep-URL guessing). Raw bodies: `/tmp/hf-cams/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET ads.atmosphere.copernicus.eu/how-to-api` → 200, 80 390 B | "If you do not have an account yet, please register … Once logged in, copy the code … `key: <PERSONAL-ACCESS-TOKEN>`" | First-party proof CAMS/ADS needs a personal account + token — dated negative, no account created |
| Official CAMS data-access factsheet (copernicus.eu) | "registration is needed … Through WebAPI a one-off key is needed" | Independent confirmation of the key gate |
| `HEAD kliimaministeerium.ee/…/Esialgne radooniriski levilate kaart.pdf` → 200 | Preliminary Rn-risk-area map exists as a static PDF | Map exists, machine feed does not |
| SSM explanatory text (stralsakerhetsmyndigheten.se) | "Radon Risk Map Set of Estonia, scale 1:500,000 … nine Map Sheets … EVS 840:2003 … >2000 survey points" | The authoritative set is paper-scale sheets, not a per-parcel feed |
| `GET remon.jrc.ec.europa.eu/…/Indoor-radon-concentration` → 200, 25 565 B | "arithmetic means (AM) over 10 km x 10 km grid cells" as a viewer product; no download/API on the page; JRC data portal shows login | 10 km grain confirms the coarse-cell shape — and the gated bulk confirms the NULL |
| `GET kik.ee/et` → 200, 348 273 B raw / ~3,2 K visible chars | Grant-program news front (food chain, EV chargers); zero visible-text mentions of jääkreostus / reostus / andmekogu / avaandmed | No open residual-pollution DB surface discoverable politely |
| `GET kese.envir.ee/` → 200, 76 255 B raw / 6 visible chars ("Kese") | JS shell, no server-rendered catalog | Storefront-level stop (p317 precedent) |
| `GET ohuseire.ee/api/v1/stations` → 404 Symfony "No route found" | The parameters3 §5.7-documented machine endpoint does not exist on the live host | Spec endpoint is aspirational, not live |
| `GET ohuseire.ee/` → 200, 54 952 B raw / 37 visible chars ("Eesti õhukvaliteedi juhtimissüsteem") | JS management-system shell, no API/download/jaam surface | Tallinn's 3 continuous stations stay human-page-only realtime |

Judgment call: the check stopped at storefront level on purpose — no
ADS account creation (explicit RULE), no KIK/KESE XHR probing, no
tender-PDF enumeration, no blind guessing of deep EGT/KIK URLs (each
miss is load on a state server). Deeper probing is exactly the scraping
this repo refuses (AGENTS.md §5).

## Near-miss proxies considered and refused

- **CAMS 10 km ensemble as a per-listing AQI gradient**: key-gated
  today; and even open, a 10 km regional cell cannot resolve streets
  (OTA PR #131 precedent). On reopen it feeds a city-baseline
  hinnang at most, never a parcel ramp.
- **JRC 10 km indoor-radon means as live p66 scores**: bulk is gated;
  the grain is right (the module's `RADON_WINDOW_M = 10 km` bakes it
  in) but the download is not. Fixtures prove the shape.
- **KIK-site proximity from OSM industrial landuse**: that is p189's
  question (mapped production land), not p204's (confirmed residual
  pollution) — relabelling it would double-score p189's map.
- **Pollen-trap density / park nearness for p137**: traps publish as
  human pages, and parks EMIT pollen — nearness inverts the question
  (nomap.md §3 G7 states the fantasy explicitly).
- **p409 agrifield footprint with seasonal meaning for p448**: a
  spatial copy with a calendar claim duplicates p409's map as fake
  harvest timing (nomap.md §3 G7).
- **Building-age proxy for p471 lead pipes**: 644/509656 = 0,13% age
  tags, zero pipe tags county-wide — noise presented as plumbing.
- **CAMS/AQI-index relabelling for p67/p252/p448/p471/p499**: an air
  number answers none of these questions (pests, species, timing,
  pipes, facades).

## What stays open (overturn path, not wired here)

An ADS anonymous tier or maintainer key, an EGT/JRC machine radon grid
(EVS classes or 10 km cells), a KIK/EELIS contaminated-sites bulk URL,
or a live Õhuseire machine API appears in-snapshot → re-open #238 with
the URL and propose the join (bands + Tallinn histogram + master, per
docs/nomap.md §2). The module's `fetch_cams_snapshot`,
`parse_radon_grid` and `parse_kik_sites` are the landing zone; bands
are first-cut and MUST be recalibrated from real counts on reopen.
Shared/group files stay untouched — the final docs-index PR updates
nomap.md.

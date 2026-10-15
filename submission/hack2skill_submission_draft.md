# Hack2skill submission draft — CarbonPilot (JAPAC AI Builder Cup 2026)

Fill this into the Hack2skill form. Numbers are verified against the live instance
2026-10-15 (see STATUS.md audit). Deadline 18 October 2026.

## Title
CarbonPilot — an AI carbon decision engine

## Tagline (one line)
From carbon accounting to carbon action.

## Category / track
Google Cloud AI Builder Cup 2026 — JAPAC (Google AI)

## Links
- Live prototype: https://rakazo-civo.tail1b51ed.ts.net:8443
- Public repository: https://github.com/glatinone/carbonpilot
- Demo video (3 min): submission/CarbonPilot_product_film.mp4
- Pitch film: submission/CarbonPilot_pitch_film.mp4
- Proposal deck: submission/CarbonPilot_submission_deck.pdf
- One-page summary: submission/CarbonPilot_one_pager.pdf

## What it is (short, ~200 words)
Companies can already measure their carbon; they still cannot decide what to do
about it. Reporting is a backward view. CarbonPilot turns fragmented operational
data (CSV electricity, cloud, travel, fleet, procurement) into prioritised,
financially-aware decarbonisation actions. Measure -> Diagnose -> Simulate -> Act,
six screens, one loop.

One architectural rule: the language model never produces a carbon number. Every
kilogram is computed by a tested deterministic engine in app/engine/; the Gemini
agent chooses which analysis to run and explains the result with cited factors.
Failure mode is "I could not find that", never "here is a plausible number".

Live result: a constraint search over 2,098 scenario combinations returns a plan
that cuts the demo footprint 33.8% (3,790 tCO2e/yr) while saving $775K/yr — 342
feasible scenarios. 138 behaviour-contract tests, 13 agent tools, bilingual EN/ID,
20 JAPAC grids benchmarked on CC BY 4.0 open data.

## Problem & motivation
The same 4,304,333 kWh load is 3,036 tCO2e on Indonesia's grid (rank 19/20, coal
69%) and 399 tCO2e in New Zealand. Location is a decision variable, not a
footnote. Most tools report where you are; none say what to do next and what it
will cost, with carbon and money in one place.

## How it works / what's built
- Ingest: CSV mapped to canonical activity types and scopes, interpretation
  confirmed before anything is written.
- Diagnose: robust median/MAD test finds the months that moved, attributes drivers.
- Simulate: interventions applied to the stored baseline; constraint search
  explores combinations (2,098 evaluated, every returned scenario satisfies the
  constraints by construction).
- Act: recommendations ranked carbon x cost x effort, weighted by factor
  confidence, tracked to an owner. Plus emissions intensity, target trajectory
  pricing, supplier lens, and course-correct plan-vs-actual.
- Stack: Next.js static export, FastAPI, SQLite, Gemini over a gateway key.
- Deploy: one systemd unit behind a Tailscale funnel; Cloud Run is the
  judging-path deployment with no architectural change.

## Tech / Google AI used
Gemini (google/gemini-3.1-flash-lite) tool-calling agent over a deterministic
Python engine; Next.js; FastAPI; SQLite; pure-stdlib BM25 retrieval. i18n EN/ID.

## Evidence
- 138 behaviour-contract tests (runnable without credentials)
- tsc --noEmit and production build clean
- Preflight READY: agent answers via real Gemini; preflight catches a silently
  dead key (it fails loudly rather than letting the UI claim Gemini while the
  router answers)

## Team
(1) — built end to end. (Add name / role here.)

## Honest boundaries
No compliance reporting (CSRD / SB 253 / CDP) yet; curated point factors; linear
scenario maths; no multi-tenancy. Stated rather than discovered by a judge.

# CarbonPilot — 3-minute demo script

Run order: backend on :8008, frontend on :3000. Reset the demo data before you present.

```bash
cd backend && .venv/Scripts/python -m app.seed --seed-db
```

---

## 0:00–0:22 — Problem

> "Companies today *can* calculate their carbon footprint. But knowing you emit eleven thousand
> tons of CO₂ doesn't tell you what to do next. Sustainability teams still stitch together
> operational data, carbon impact, cost and feasibility by hand."

*Screen: an empty dashboard.*

## 0:22–0:45 — Product

*Show the dashboard.*

> "This is **CarbonPilot**, an AI carbon decision engine. It turns operational data into
> measurable actions: **Measure, Diagnose, Simulate, Act.**"

Point at the hero number: **11,208 tCO₂e/year** across 168 activity records, 12 months, Scope 1/2/3
split.

## 0:45–1:10 — Upload (only if you have the slide ready)

> "Input is whatever the company already has — CSV exports from electricity, cloud billing,
> travel and fuel."

Click **Analyze** on the Ask panel with:

> *"Where are our biggest emissions?"*

The agent calls `get_baseline` then `get_emission_breakdown` and answers with the real split.
Point at the **tool-call trace** under the answer:

> "Notice the model didn't do arithmetic. It chose the tools; the calculation engine produced
> every number."

## 1:10–1:35 — Diagnose

Go to **AI Insights**.

> "CarbonPilot found three signals. The big one: cloud compute rose 165% in May."

Expand it.

> **Why?** → *"The weekend share of cloud usage rose from 15% to 62% — four times the previous
> baseline."*

> "That is an AI agent chaining statistical detection, period comparison and driver attribution —
> not a chatbot summarising a chart."

## 1:35–2:05 — The WOW moment

Go to **Simulator**. Drag **Right-size weekend cloud workloads** to 30%.

> "Estimated impact: **−57 tCO₂e/year** and roughly **−$3.0M/year** in cloud spend, effort medium."

Then use **Constraint search**:

> *"But here's the real question a CFO asks. Reduce our carbon by 15% without increasing
> operating cost."*

Set min. carbon reduction = **15%**, max cost increase = **0**, click **Find scenarios**.

> "The engine evaluated [N] combinations and returned the ones that satisfy both constraints —
> with the carbon, the cost, the effort and a confidence score for each."

## 2:05–2:30 — Act

Go to **Action Plan**.

> "Recommendations are ranked by carbon × cost × effort, weighted by confidence — not by whichever
> bar is biggest. A 460-tonne retrofit that saves $74K and is easy to ship outranks a huge
> renewable PPA that costs money and takes two years."

Click **Create Action**, assign the owner.

> "Approved recommendations become owned, tracked actions with their expected impact attached."

## 2:30–2:52 — Technology credibility

> "Under the hood: the LLM interprets messy data, decides which analysis to run, and explains the
> result. It never produces a carbon number. The calculation engine multiplies activity data by a
> cited emission factor — UK Government conversion factors, Cloud Carbon Footprint methodology,
> the Indonesian grid factor — and every recommendation carries its evidence, its assumptions and
> an uncertainty-derived confidence score."

## 2:52–3:00 — Close

> "Carbon reporting tells you where you are. **CarbonPilot tells you what to do next.**"

---

## Rehearsal checklist

Run the preflight first — it exercises every route behind the four pages, the constraint search
and one real agent question, and fails on anything that would break on stage:

```bash
cd backend && ./.venv/Scripts/python.exe scripts/preflight.py --reset
```

`--reset` re-seeds the synthetic dataset (clearing actions and scenario history) before checking,
so one command both resets and verifies. It prints `READY` and exits 0, or names the failing
check. Fix anything it reports, then work through the rest by hand:

- [ ] Backend reachable on http://localhost:8008/api/health with `"llm_mode": "gemini"`.
      If it says `offline`, the UI will label answers `Deterministic engine` — add the key or
      acknowledge the deterministic mode out loud; do not let a judge discover it on screen.
- [ ] Frontend loaded at http://localhost:3000, and the Ask panel already answered once (proves
      the round trip works before you're on stage)
- [ ] Simulator sliders reset to 0
- [ ] Action Plan cleared of stale actions from rehearsal
- [ ] One backup screenshot of each of the four pages, in case the network drops

`next start` is not a supported way to serve the UI here (see backend/README.md) — use
`npm run dev` against the API, or the single-port static export.

## Numbers to have ready if a judge pushes

| Question | Answer |
|---|---|
| "Is the LLM hallucinating these?" | No — every figure comes from a tool call shown on screen. The model's job is tool selection and explanation. |
| "How accurate are the factors?" | Curated point estimates with published sources and an uncertainty band per factor; production would use Climatiq or the issuing authority's live factors. |
| "Why is cloud only ~2% of emissions?" | Because per-vCPU-hour intensities genuinely are small (Cloud Carbon Footprint). It's 29% of *spend* though — which is why the decision layer, not the accounting layer, is the product. |
| "What's fake here?" | The company and its activity data are synthetic. The methodology, the emission factors, the statistics and the engines are real. |
| "Can it read our real data?" | Yes — CSV upload, long or wide format, with a semantic mapping preview before anything is calculated. |

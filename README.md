# NEXUS — Agricultural Decision Intelligence for FPOs

**Find the problem. Understand the evidence. Recommend the next move.**

A data-grounded AI decision-support platform for **Farmer Producer Organizations (FPOs)**: identify produce at risk of spoilage, assess where and when to sell, compare wholesale markets, estimate transport and storage costs, and explain the trade-offs with traceable evidence.

Built for the **Open Agent Hackathon 2026**.

> **Submission integrity:** This is a working prototype built around a synthetic agricultural dataset, not a deployed live production system. Database and unit-test success do not mean that every external API is working at all times. Decisions requiring missing or stale price, route, or cost evidence must be presented as conditional, not guaranteed profit.

## The problem: post-harvest losses in India

> **India's agricultural post-harvest losses are significant.** A Government of India–commissioned **NABCONS (2022)** study estimated losses of **4.87%–11.61% for vegetables** and **6.02%–15.05% for fruits**, depending on the commodity. These are *commodity-specific post-harvest loss estimates*, not a single annual wastage percentage or a claim that NEXUS can eliminate all of them.

**Official sources:**
- [Ministry of Food Processing Industries / Press Information Bureau — Post Harvest Food Loss (20 December 2022)](https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=1885038)
- [Ministry of Food Processing Industries — Annual Report 2024–25, section 2.6 / Table 2.11](https://www.mofpi.gov.in/sites/default/files/mofpi_annual_report_2024-25_english_21.08.2025.pdf)

Behind those estimates are practical problems: harvested vegetables have a limited saleable life; farmers may lack timely access to reliable prices, suitable buyers, transport and storage; delays and spoilage reduce the value recovered from their work. Aggregation helps, but it doesn't automatically answer where, when or whether an FPO should sell its inventory.

### Our proposed farmer-to-FPO model

1. **Farmers harvest crops.** Finding individual buyers and arranging storage or transport can be difficult, especially for perishables.
2. **The FPO buys or aggregates produce.** Under an agreed procurement arrangement, farmers can receive payment from the FPO without individually managing the onward wholesale sale. **Payment timing and terms depend on the actual FPO arrangement; NEXUS does not process or guarantee payment.**
3. **The FPO records its stock.** Harvest dates, batch IDs, quantities, warehouses, procurement and storage expenses, and spoilage risk are stored in the operational data system.
4. **NEXUS analyzes the next move.** It makes tool calls to retrieve batch facts through **Zetaris + PostgreSQL**, obtain available mandi prices, calculate **OpenRouteService** routes and **Open-Meteo** weather, and run deterministic financial comparisons. **Meterless/Nightshift + NVIDIA Nemotron** can explain the grounded recommendation when the configured runtime succeeds.
5. **The FPO decides and dispatches.** It compares feasible markets, buyer acceptance, travel and delivery time, quality deterioration, total costs and recoverable proceeds. The goal is **higher feasible net returns or smaller avoidable losses**, not blindly chasing the highest displayed wholesale price.

### What NEXUS is trying to change

A warehouse might hold several tonnes of tomatoes that have only a short quality window left. Selling locally may be fast but yield a lower price; driving farther may offer a higher quote but also increase time, transport cost and spoilage risk. **NEXUS is designed to make that trade-off visible before the produce loses more value.**

**Mission:** reduce preventable post-harvest losses, support smarter FPO selling decisions, and help agricultural communities recover more value from harvested produce. NEXUS is a decision-support prototype—not a guarantee of profit, farmer payment or zero crop waste.

---

## Why this matters

A farmer or FPO operator may have tonnes of tomatoes approaching the end of their saleable window. The nearest mandi is not always the most profitable; the market with the highest quoted price might be too far away, involve costly transport, or expose produce to deterioration. A useful decision must combine **inventory, quality risk, market price, journey time, transport cost, storage cost, and uncertainty** rather than answer with a generic “sell now.”

NEXUS aims to help operators:
- Discover which crop batches require urgent attention, including quantity, harvest date and warehouse.
- Compare plausible destinations such as Baramati, Pune, Mumbai and Nashik.
- Assess whether to dispatch immediately or store temporarily.
- Estimate recoverable proceeds, incremental expenses, spoilage exposure and possible profit/loss.
- Ask follow-ups like “Where should I sell those batches?” without losing the selected crop and batch context.
- Inspect which evidence and calculations support a recommendation.

## End-to-end approach

\`\`\`text
FPO operator (natural-language question)
       |
       v
NEXUS React AI Workspace
       |
       v
Agricultural intent + session context
       |
       v
Typed NL-to-SQL planner / allowlisted read-only queries
       |
       v
Zetaris semantic/query gateway --> PostgreSQL FPO data & analytical views
       |
       +--> Government mandi prices (data.gov.in / AGMARKNET, if available)
       +--> Road routes (OpenRouteService, if configured)
       +--> Weather forecasts (Open-Meteo)
       |
       v
Deterministic financial and risk calculations (Python Decimal)
       |
       v
Meterless / Nightshift routing --> NVIDIA Nemotron explanation
       |                         --> configured fallback when unavailable
       v
Evidence validation --> Recommendation, alternatives, sources, warnings
\`\`\`

**The database is the source of inventory facts. The finance engine owns arithmetic. The AI model explains evidence, not invents missing batch IDs, rupee amounts or prices.**

## Sponsor and technology integrations

| Technology | How NEXUS uses it | Implementation / evidence |
|---|---|---|
| **Zetaris** | Query gateway for the registered PostgreSQL FPO source; safe SELECT-based batch inventory and analytical retrieval | \`backend/tools/zetaris.py\`, \`backend/tools/nl_to_sql.py\`; reported connection and SELECT 1 success. A successful SELECT 1 alone is not proof of a complete FPO inventory query. |
| **PostgreSQL** | FPOs, farmers, crops, harvest batches, warehouses, inventory, prices, routes, storage and analytical views | Schema migrations and synthetic dataset in the repository. Data is for demonstration, not genuine farmer records. |
| **Meterless Engine / Nightshift** | AI routing/orchestration layer with a local Windows runtime and NVIDIA cloud lanes | \`backend/tools/meterless.py\`; successful Nightshift CLI/NVIDIA adapter tests reported. NEXUS-to-runtime end-to-end execution needs a verified trace. |
| **NVIDIA Nemotron** | Explain evidence, compare risk/finance outcomes and support agent workflows | \`backend/tools/nvidia_nemotron.py\` and Nightshift cloud-lane configuration. See model roles below. |
| **OpenRouteService / OpenStreetMap** | Road geocoding, directions, distance/time and transport-cost inputs | \`backend/tools/routing.py\`; live Baramati→Pune/Mumbai/Nashik route checks reported. Fuel, loading, toll and vehicle expenses must be checked or labelled assumptions. |
| **Open-Meteo** | Forecast temperature, humidity and rainfall; inputs to crop-specific risk estimates | \`backend/tools/weather.py\`; reported live 7-day forecast checks and cache repair. |
| **data.gov.in** | Government wholesale mandi-price observations, market/commodity filtering, timestamps and unit conversion | \`backend/tools/live_market_prices.py\`. **Latest reported live state: HTTP 500; not verified usable.** |
| **AGMARKNET** | Secondary official wholesale-price source, parsed and freshness-labelled when available | \`backend/tools/live_market_prices.py\`. **Latest reported live state: no usable observations.** |
| **Cursor** | Sponsor tool evaluated as a potential development option | **Not used for implementation.** We did not establish how to claim/use the offered credits in time, so we make **no Cursor integration or credit-usage claim**. |
| **OpenCode** | AI-assisted code development and debugging | Used during NEXUS development; Nemotron 3 Ultra 550B A55B was selected for development sessions. This is **developer tooling**, distinct from the runtime inference provider used by NEXUS. |

### NVIDIA models and roles

NEXUS uses an extensible model/provider design. The following are the relevant models discussed or configured; **configured, supported and live-tested are not interchangeable**.

| Model | Intended role | Verification caveat |
|---|---|---|
| **Nemotron 3 Ultra 550B A55B** (\`nvidia/nemotron-3-ultra-550b-a55b\`) | Primary high-complexity agricultural explanation/decision reasoning; also used for development in OpenCode | Direct NVIDIA and Nightshift adapter calls were reported successful. A Nightshift Ultra *Race* lane was configured and generated attempts. A complete NEXUS agricultural inference trace is the final proof. |
| **Nemotron 3.5 Lightning 30B A3B** | Faster agent reasoning and possible verification duty | Direct + Nightshift adapter diagnostics were reported successful. Verify actual lane/job execution separately. |
| **Nemotron 3.5 Bolt E4B** | Lightweight planning, classification and tool-focused steps | Supported in the existing NVIDIA agricultural adapter; use only when actually selected/configured. |
| **Nemotron 3 Super / other catalog models** | Optional future experiments, not required for demo | Catalog availability does not prove successful invocation. |

Nightshift model selection and duty assignment are runtime settings. An Ultra Race lane is not by itself evidence of a working Judge/Verify lane or a completed end-to-end application run. Cloud-hosted trial endpoints may be rate limited or credit limited.

## Agricultural decision pipeline

1. **Understand.** Detect inventory, spoilage, market selection, hold-vs-sell, finance or logistics intent; resolve relevant context from earlier conversation turns.
2. **Retrieve.** Generate typed, schema-aware, read-only queries via Zetaris to obtain actual FPO batch records. Label any explicitly enabled PostgreSQL fallback correctly.
3. **Enrich.** Query government market sources, road routes and weather as configured. Preserve observation dates, units and source identifiers; flag stale or unavailable evidence.
4. **Calculate.** Use deterministic arithmetic for quantity, revenue, logistics, storage, spoilage assumptions and estimated net proceeds. Distinguish already-incurred procurement costs from incremental dispatch decisions.
5. **Reason.** Pass structured evidence and computed outcomes to the configured Meterless/Nightshift/NVIDIA reasoning path. Avoid granting the model authority to alter financial numbers.
6. **Validate and present.** Explain feasibility, financial trade-offs, alternatives, missing inputs and next actions with evidence and execution status.

Relevant implementation: \`backend/tools/fpo_decision_agent.py\`, \`backend/tools/nl_to_sql.py\`, \`backend/tools/live_market_prices.py\`, \`backend/tools/routing.py\`, \`backend/tools/weather.py\`, \`backend/tools/meterless.py\`, \`backend/tools/nvidia_nemotron.py\`.

## Three reproducible demo inputs

These are **example prompts**, not fabricated screenshots or invented live outputs. Run them against the active stack and attach the real results and redacted execution traces before submitting.

### Example A — Critical batch inventory

**Input**
> Show the five tomato batches with the highest spoilage risk from Zetaris. Include batch ID, saleable quantity, harvest date, warehouse and risk level. Show the executed query source.

**Expected evidence/response**
- A table of actual matching batch records, sorted by risk/urgency.
- Zetaris query status, source, retrieval time and row count.
- If the query fails, a specific error rather than a generic “Sell Now” answer.

### Example B — Market selection with follow-up context

**Input**
> For those five tomato batches, compare feasible sale destinations in Pune, Mumbai and Nashik. Where should we dispatch first, and why?

**Expected evidence/response**
- Retained batch IDs and origin locations from Example A.
- Dated wholesale-price observations if available, route distances/durations, cost assumptions and risks.
- A supported destination comparison or a transparent statement that current market evidence prevents ranking.
- Trace of provider/model execution if the AI reasoning stage actually runs.

### Example C — Urgent sell-vs-hold scenario

**Input**
> Scenario only: We harvested 8,000 kg of hybrid tomatoes on 23 October 2026. As of 27 October, 7,200 kg remain saleable in a non-refrigerated Baramati warehouse at an operator-reported 29°C. Storage costs ₹700 per tonne per day, procurement was ₹12/kg, and quality may last less than 24 hours. A truck holds 5 tonnes, fuel efficiency is 5 km/litre, assumed fuel price is ₹95/litre, and driver/loading cost is ₹3,000 per trip. Compare Baramati, Pune, Mumbai, Nashik and storing one more day. Use actual available prices, routes and weather. Identify the best feasible option or what data is missing to choose.

**Expected evidence/response**
- Clearly identifies all supplied values as **operator-provided scenario assumptions**, not a real Zetaris batch.
- Accounts for at least two vehicle loads to move 7.2 tonnes with 5-tonne capacity.
- Compares available road distances, market prices and costs without inventing unavailable values.
- Shows recoverable net proceeds and break-even thresholds where possible, including uncertainty.

**Suggested demo walkthrough (approximately three minutes):** problem and stakes → Zetaris/PostgreSQL data → batch risk → market/routing/weather evidence → Nightshift/Nemotron trace → calculation, recommendation and limitations.

## Current prototype status and limitations

The most recent reported audit (commit \`da053fd\`) states:
- **119 backend tests passed, 6 skipped**, with a successful frontend production build. Earlier reports used different test-discovery totals; do not combine them into one unsupported number.
- PostgreSQL agricultural analytics endpoints returned results; Zetaris connection and SELECT 1 succeeded.
- OpenRouteService returned example route distances of approximately **87 km (Baramati–Pune), 207 km (Baramati–Mumbai), and 221 km (Baramati–Nashik)** during that audit. These are observations from the test, **not guaranteed real-time traffic-aware journey estimates**.
- Open-Meteo returned weather forecasts.
- NVIDIA Ultra responded to direct/adapter requests; the Nightshift lane produced model attempts.
- **data.gov.in returned HTTP 500 and AGMARKNET supplied no usable observations in that run**; no real mandi-price-dependent profit ranking should be claimed on that evidence.
- The full NEXUS → Zetaris → Meterless Engine → Nightshift → NVIDIA → validated recommendation demo still requires a recorded successful execution trace, if not already captured.

Synthetic data is used to demonstrate the workflow. Government observation dates, forecasts, transport assumptions and live service availability can change. NEXUS is decision support, not a guaranteed sale, buyer acceptance, or financial return.

## Technology stack

- **Backend:** Python, FastAPI, read-only SQL planning, deterministic Decimal calculations
- **Data:** PostgreSQL, Zetaris Lightning/query gateway, seeded FPO agricultural schema and views
- **AI:** Meterless/Nightshift runtime, NVIDIA NIM/Nemotron, explicit fallback behavior
- **External intelligence:** data.gov.in, AGMARKNET, OpenRouteService, Open-Meteo
- **Frontend:** React 18, Vite, charting and agricultural intelligence screens
- **Environment:** Windows development, Docker-based database/Zetaris stack

## Local setup

### Prerequisites

Windows with Python and Node.js/npm, Docker Desktop for the PostgreSQL/Zetaris stack, and a functioning Nightshift installation for AI routing. External services require connectivity and their respective credentials.

\`\`\`powershell
git clone https://github.com/TAHA-SHAIKH27/NEXUS.git
cd NEXUS
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
\`\`\`

Start the repository's existing PostgreSQL/Zetaris Docker Compose stack and confirm the FPO datasource is registered in Zetaris. **Do not erase volumes or reseed an existing database just to start services.**

Run the backend and frontend in separate terminals:

\`\`\`powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
\`\`\`

\`\`\`powershell
npm run dev
\`\`\`

- React development UI: \`http://localhost:5173\` (see \`vite.config.js\`).
- FastAPI: \`http://127.0.0.1:8000\`
- Zetaris UI: typically \`http://localhost:3000\` in the local Docker setup.
- Nightshift OpenAI-compatible base URL: \`http://127.0.0.1:8088/v1\` when its runtime is active.

These are local development addresses, not hosted public demo URLs.

### Configuration

Use the NEXUS Settings UI / secure local backend configuration for relevant fields:
- \`zetaris_base_url\`, \`zetaris_username\`, \`zetaris_password\`, \`zetaris_org_id\`
- \`meterless_base_url\`, \`meterless_runtime_token\`, \`meterless_app_id\`, routing mode
- NVIDIA API key and selected agricultural reasoning model
- OpenRouteService API key
- data.gov.in API key (and valid dataset/resource ID where supported)

Nightshift's proxy token and NVIDIA API key are **different credentials**. Never paste either into README, screenshots, issue reports, or Git. Local \`config.json\`, tokens and state must remain excluded from Git. Review history for exposed secrets and rotate any that were exposed.

A saved key means *configured*, not necessarily *connected*. Verify real authenticated requests and log redacted status codes and trace IDs. Avoid storing browser-side raw secrets.

## Development workflow and credits disclosure

NEXUS was built iteratively using an AI-assisted coding workflow with **OpenCode**, including use of **NVIDIA Nemotron 3 Ultra 550B A55B** for development assistance. The product runtime and development assistant are separate: using Ultra to help write code is not proof that the deployed NEXUS assistant invoked Ultra for a given response.

We explored the **Cursor** sponsor option but **did not use Cursor for the implementation** because the team could not confirm the credit redemption/setup process in time. We do not claim Cursor sponsor usage, credits, or bonus eligibility.

We used **Zetaris** to bridge the FPO PostgreSQL source with the agricultural query layer and **Meterless/Nightshift** as the intended provider/orchestration interface for NVIDIA-hosted models. Actual sponsor-technology usage should be demonstrated by query results, runtime receipts and redacted traces, not badges alone.

## Verification, contributions and license

Run the project's test suite and frontend build before merging changes:

\`\`\`powershell
python -m pytest -q
npm run build
\`\`\`

Do not commit credentials, real personal/farmer data, browser sessions or private logs. Preserve reproducible examples and indicate when evidence is synthetic, unavailable, or stale.

See \`HACKATHON_2026_IMPLEMENTATION_PLAN.md\` for implementation history and outstanding integration checks.

**License:** No license is declared here; repository content remains subject to applicable copyright until the owner chooses a license.

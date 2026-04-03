# Use Case: Property Acquisition Analysis

A non-technical application of the Lyra Agent Platform — assisting a small real estate investor or property fund with due diligence on potential property acquisitions.

---

## The Problem

A small property investor evaluates 5–10 potential acquisitions per month. For each property they need:
- Market analysis (comparable sales, rental yields, area trends)
- Financial modeling (cash flow projections, ROI scenarios)
- Risk assessment (regulatory, structural, market cycle)
- A concise investment memo for partners or lenders
- Sometimes a translated summary for international co-investors

Currently this takes 4–6 hours per property of manual research and spreadsheet work, often done by the investor personally. The quality varies depending on fatigue and time pressure. Some deals get shallow analysis because there isn't time to go deep on everything.

## The Setup

### MCP Servers

- `filesystem` — read property data files (PDFs exported to text, CSV financials, photos metadata), write reports
- `shell` — run calculation scripts, format outputs

### Skills

```
skills/
├── cash-flow-projection.md    # Generate 5-year cash flow from purchase price, rent, expenses
├── comparable-analysis.md     # Structure comparable property analysis from market data
├── risk-matrix.md             # Produce a risk matrix with likelihood/impact scoring
├── investment-memo.md         # Generate a 1-page investment memo from analysis
├── tenant-profile.md          # Assess tenant quality from lease terms and market
├── renovation-estimate.md     # Estimate renovation scope and cost from property description
├── exit-strategy.md           # Model exit scenarios (hold, flip, refinance)
```

The investor creates these skills as they discover recurring analysis patterns. The first property analysis takes longer — by the fifth, the skills library handles most of the heavy lifting.

### Agent Templates

```
prompts/
├── deal-coordinator.json/md       # Orchestrates full property analysis
├── market-analyst.json/md         # Researches market conditions and comparables
├── financial-modeler.json/md      # Cash flow, ROI, sensitivity analysis
├── risk-assessor.json/md          # Identifies and scores risks
├── memo-writer.json/md            # Produces investor-ready documents
```

**deal-coordinator** — receives a property brief (address, asking price, basic details). Searches templates, spawns specialists, orchestrates the pipeline, assembles the final package.

**market-analyst** — filesystem access to read market data files. Produces structured market analysis: comparable sales, rental yields, vacancy rates, area demographic trends, supply pipeline.

**financial-modeler** — pure reasoning. Takes property details and market data, produces cash flow projections, cap rate analysis, debt service coverage, IRR under multiple scenarios (base, upside, downside). Low temperature (0.2) for precision.

**risk-assessor** — pure reasoning. Identifies risks across categories: market (cycle timing, oversupply), property (structural, environmental, zoning), financial (interest rate sensitivity, vacancy), regulatory (rent control, planning restrictions). Scores each risk. Uses the risk-matrix skill.

**memo-writer** — pure reasoning. Takes all analysis and distills it into a 1-page investment memo with recommendation (Buy / Pass / Negotiate). Higher temperature (0.5) for clear, persuasive writing.

## The Flow

```
User: "Analyze this property for acquisition:
       - 3-bedroom flat, Prague 7 Holesovice
       - Asking price: 8.5M CZK
       - Current rent: 25,000 CZK/month
       - Built 1935, renovated 2018
       - Tenant in place until 2026"

deal-coordinator:
  1. list_templates(query="market research") → finds market-analyst
  2. list_templates(query="financial modeling") → finds financial-modeler
  3. recall(query="Prague 7 property market") → checks existing knowledge
  4. spawn_agent(template="market-analyst", task="Research Prague 7
     Holesovice residential market: comparable 3-bedroom flat sales
     in the last 12 months, current rental yields, area trends,
     planned development...")
  5. spawn_agent(template="financial-modeler", task="Model acquisition
     of 3-bed flat at 8.5M CZK, current rent 25K/month, estimate
     expenses, project 5-year cash flow, calculate ROI under 3
     scenarios...")
     — both run in parallel (independent research)
  6. wait for both → collect market analysis + financial model
  7. spawn_agent(template="risk-assessor", task="Assess risks for
     this acquisition based on: {market_analysis} {financial_model}
     Property details: 1935 building, renovated 2018, tenant
     until 2026...")
  8. Use investment-memo skill to produce 1-page memo
  9. Use exit-strategy skill to model hold vs flip vs refinance
  10. Write full package to work/deals/prague7-holesovice-3bed/
      ├── market-analysis.md
      ├── financial-model.md
      ├── risk-assessment.md
      ├── investment-memo.md
      └── exit-scenarios.md
  11. Optionally: spawn translator for English version for
      international co-investor
```

## What Makes This Actually Useful

**Parallel analysis.** Market research and financial modeling run simultaneously, cutting analysis time. Risk assessment then builds on both — a natural pipeline.

**Memory builds a knowledge base.** After analyzing 5 properties in Prague 7, the platform has accumulated: average price per sqm, typical rental yields, vacancy rates, regulatory environment, comparable transactions. The 6th analysis starts with context the first one didn't have. Over time the system becomes a domain expert in the investor's target market.

**Skills encode the investor's methodology.** The cash-flow-projection skill uses their specific assumptions: maintenance reserve percentage, vacancy allowance, management fee structure, tax treatment. Every property gets analyzed the same way — no shortcuts under time pressure.

**Consistent output format.** Every deal gets the same package: market analysis, financial model, risk assessment, investment memo, exit scenarios. Partners and lenders see a professional, standardized output regardless of which property is being evaluated.

**Quick screening.** For properties that are clearly overpriced, the coordinator can run just the financial modeler — if the numbers don't work at asking price, no need for full analysis. The orchestration adapts to the situation.

**Audit trail.** Every analysis is fully traceable via the event timeline: which data was used, which assumptions were made, which models were run. If a lender asks "how did you arrive at this cap rate?" the answer is in the events.

## What You'd Need to Build

1. **7 skill files** — the investor's analytical templates (~1 hour)
2. **5 template files** — agent prompts for each specialist role (~1 hour)
3. **Property data** — the investor would need to provide property details as text files or structured input
4. **Nothing else** — orchestration, parallel execution, memory, file output all exist

## What It Doesn't Do (Yet)

- Can't scrape property portals (would need a web scraping MCP server)
- Can't pull live market data APIs (would need an API client MCP server)
- Can't process photos (would need a vision model integration)
- Can't generate Excel spreadsheets (would need a spreadsheet MCP server or Python script skill)
- Financial projections are LLM-generated estimates, not spreadsheet-precise calculations

The first two limitations are solvable with additional MCP servers (V3P2). The spreadsheet limitation could be addressed with a skill that generates Python calculation scripts run via the shell MCP server — the infrastructure for this already exists.

## Why This Isn't Just ChatGPT

A single ChatGPT conversation could produce a property analysis. The difference:

- **Specialization.** Each sub-agent has a focused role with appropriate temperature and context. The financial modeler is precise (temp 0.2); the memo writer is persuasive (temp 0.5). A single model in a single conversation blurs these.
- **Parallel execution.** Independent analyses run simultaneously, not sequentially in one thread.
- **Persistent knowledge.** The tenth property analysis benefits from memories of the first nine. ChatGPT starts from zero every conversation.
- **Reproducible methodology.** Skills encode the investor's specific analytical framework. ChatGPT adapts to whatever you ask — which means inconsistency.
- **Full audit trail.** Every step is logged, timed, and traceable. A ChatGPT conversation is a text transcript, not an event-sourced analytical record.

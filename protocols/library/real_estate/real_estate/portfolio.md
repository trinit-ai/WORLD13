# PORTFOLIO DASHBOARD — Multi-Property Cartridge
# Aggregate view across multiple properties. Uses data from Rental and Flip analyses.

---

## ENGINE SHOWCASE
Cross-cartridge state aggregation. The portfolio pulls from every property analyzed in the Rental cartridge and computes portfolio-level metrics. Demonstrates the engine managing complex cross-module state.

---

## ENTRY

If no properties analyzed yet:
"Portfolio is empty. Analyze a rental property first, then you can add it here."

If properties exist:
Show the dashboard immediately. No preamble.

---

## DASHBOARD

:::card
**Portfolio Summary — [N] Properties**

| Property | Value | Equity | Cash Flow | Cap Rate |
|----------|-------|--------|-----------|----------|
| [Property 1] | $250K | $62K | -$156/mo | 5.0% |
| [Property 2] | $180K | $45K | +$220/mo | 7.8% |
| [Property 3] | $320K | $98K | +$150/mo | 5.5% |
| **Portfolio** | **$750K** | **$205K** | **$214/mo** | **5.9%** |

*Cash flow and cap rates reflect current rate assumptions (6.0% 30yr fixed).*
:::

### Portfolio Insights

After showing the dashboard, offer 1–2 observations in plain text. Pick the most important:

- Concentration risk: "Property 3 is 48% of your equity. If that market dips, it hits hard."
- Cash flow dependency: "Property 2 is carrying the portfolio. If it vacates, your net cash flow goes negative."
- Performance drag: "Property 1 is bleeding $156/month and dragging the portfolio cap rate below 6%. It's the weakest link."
- Diversification note: "All three are in the same market. Geographic diversification would reduce your exposure."

Don't give all of these. Pick the one or two that matter most for this specific portfolio.

### What-If Scenarios

If the user asks, model:
- Selling a property (impact on portfolio cash flow and equity)
- Adding a new property (how it changes the aggregate)
- Refinancing one property at a lower rate
- Cash-out refi on one to fund a down payment on the next

---

## ADDING PROPERTIES

Properties enter the portfolio from the Rental cartridge:
"Add this to portfolio" after any rental analysis.

Or manually: "Add a property — just give me value, equity, and monthly cash flow."

---

## POST-ANALYSIS

After showing the dashboard and insights, ask one question:

- If portfolio has a weak property: "Want to dig into [weakest property] and see what would fix the numbers?"
- If portfolio looks solid: "Want to model what adding another property would do?"
- If they have only one property: "Want to analyze another property to build the comparison?"

One question. Let the user pull for more.

# Analytics page — which graphics actually matter, and why

A full inventory of every graphic on the Analytics → Overview tab
(`_AnalyticsOverview` in `main.py`), reviewed for whether it earns its space in
a personal budgeting app. 15 distinct visual elements are stacked on one
scrollable page today: 2 tile rows, 1 table, and 10 charts/lists. That's a lot
— this doc sorts them into **essential**, **useful but secondary**, and
**redundant/low-value**, with the reasoning for each, so future changes (cut,
resize, keep) have a documented rationale instead of gut feel.

---

## Tier 1 — Essential (the core budgeting/finance questions)

### 1. Budget vs actual — `self.bva` (GroupedBarChart)
**Answers:** "Am I sticking to my budget, category by category, this month?"
This is the single most direct feedback loop a budgeting app can offer — every
other chart on this page is either upstream context (where did money come
from) or downstream analysis (how did last month go). This is the one that
changes behavior *this month*, before it's too late to course-correct.
Correctly has an onboarding empty-state (`_bva_empty`) instead of rendering a
wall of red bars when no category budgets are set, and a direct "Set
budgets…" affordance in its own header — the fix that closed the "all-red by
default" bug from the earlier UX critique. Recently promoted to full width
(was sharing a row with "Spending by tag") specifically because this is a
Tier 1 chart.

### 2. Spending composition — last 6 months — `self.stacked` (StackedBarChart)
**Answers:** "Where does my money actually go, and is that changing?" This is
the one chart that shows category *and* trend simultaneously — a stacked bar
per month, colour-coded by category, with a hover-linked legend. Every other
"where does money go" view on this page (donut, spending-by-tag) only shows
one month or one axis; this is the only one that shows drift over time, which
is what actually matters for changing a habit. Minimum height raised
230→260px in the last pass.

### 3. Net worth — history — `self.area` (AreaChart)
**Answers:** "Is my wealth actually growing?" The single long-run "is this
working" chart on the page — assets and liabilities plotted separately with
net worth as a bright overlay line. Every other chart here is monthly-cadence
(this month, last 5 months, last 6 months); this is the only one with a
genuinely long horizon, which is the timeframe net worth actually needs to be
judged on. Paired with #4 below by design (same chart family, same new 240px
minimum height — previously unset entirely, meaning it likely rendered at an
under-sized default).

### 4. Liquid-balance forecast — next 6 months — `self.fan` (FanChart)
**Answers:** "Will I run out of cash soon?" Arguably the single most
*actionable* chart on the page — it's the only one that looks forward at the
account-balance level (not just P&L) and explicitly shades below zero. A
budget can look "fine" on average while a specific week still overdraws the
account; this is the chart that would actually catch that. Same treatment as
#3: newly given an explicit 240px minimum.

### 5. Month by month — table, not a chart
**Answers:** the fastest literal numeric glance: income / expenses / P&L /
savings-rate per month, one row each. Deliberately placed near the top of the
page (a comment in the code says exactly this: "it's the fastest 'am I on
track' glance… shouldn't require scrolling past a dozen charts to reach").
Each month label is clickable and drives the same drill-down as the P&L
trend chart (see #6) — this table is a second entry point into that
interaction, not just a static readout.

---

## Tier 2 — Useful, but secondary (real utility, lower priority than Tier 1)

### 6. P&L vs target — last 5 months (LineChart, click-to-filter)
This looked, at a glance, like a third redundant restatement of the P&L trend
already in the table and in "Income vs Expenses" below. It isn't, quite:
clicking a point calls `_on_trend_click` → `_show_breakdown`, which re-targets
the donut chart (#14) and income-sources list (#15) to that specific month.
So this chart (and the Month-by-month table, #5) are the two entry points
into a genuine drill-down feature — "click any past month, see its expense
breakdown and income sources." That's real, non-decorative interactivity, and
it's why this survives as Tier 2 rather than Tier 3: the *trend line itself*
somewhat restates the table, but the *interaction* it carries is unique.

### 7. Predicted income — next 6 months (recurring sources)
Forward-looking, income-side complement to the (expense-focused) budget
chart. Useful for anyone whose income varies or who wants to sanity-check
next month before it arrives. Secondary only because for most users with
stable salaried income this rarely surprises — the number rarely moves month
to month (confirmed in the demo data: every month currently shows the
identical $5,880 predicted figure).

### 8. Expense breakdown (donut) + Income sources — `self.donut` / `self.inc_card`
Not decorative on their own merits — as covered under #6, these are the
*output* of the drill-down interaction, always showing the currently-selected
month (defaults to the current month on load). The category donut and the
stacked composition chart (#2) do overlap in what they show for the *current*
month specifically, but the donut's actual job is being the answer to "tell
me about a month I just clicked," not a second always-on view of this month.
Kept as Tier 2 because that job is real, even though the current-month
default view is redundant with #2.

---

## Tier 3 — Redundant, decorative, or conditionally dead

### 9. Cash flow — this month (SankeyChart)
Visually the most striking chart on the page, and the least informative one.
A Sankey diagram earns its complexity when a flow has many nodes and
non-obvious paths; here it's ~4 income sources flowing into "Cash" and back
out to ~7 expense categories — a flow simple enough that the stacked bar (#2)
or the donut (#8) already show the same allocation with less chart to parse.
Keep it if it's genuinely liked for its look; cut it first if the page needs
to get shorter.

### 10. Spending by tag — this month (bar list)
A second, tag-based cut of "where did money go," alongside the
category-based composition chart (#2) and donut (#8). Tags and categories
are two different taxonomies in this app's data model (a node can carry both
`category` and `tags`), so this isn't strictly duplicate data — but it's a
third lens on the same underlying question, and for most users tags and
categories will overlap heavily in practice (the demo data's only tags are
"Home" and "Fixed," subsets of what the categories already imply).

### 11. Income vs Expenses — all months (LineChart)
The purely decorative sibling of #6 — same two series (income, expenses)
plotted as a dual line, but with no click interaction and no distinct
question it answers that the Month-by-month table doesn't already answer
more precisely (exact numbers beat eyeballing a line chart for this
specific comparison). The most cuttable chart on the page after the Sankey.

### 12. Plan vs actual — this month (`self.rec_box`)
**Conditionally dead**, not just secondary: it only renders anything useful
when `budget_report(...)["has_txn"]` is true — i.e., only after a bank
statement (CSV/OFX) has been imported via the beta "Connect bank accounts"
flow in Settings. For any user who hasn't set that up (plausibly most users,
given it's explicitly labeled "beta"), this card is permanently just a
one-line prompt to go import a bank file. Worth keeping *if* bank sync is a
feature you want to drive adoption of; otherwise it's dead weight for the
common case.

---

## Summary table

| # | Graphic | Tier | One-line reason | Status |
|---|---|---|---|---|
| 1 | Budget vs actual | **1** | The core "am I on budget" loop | Kept, full width, accent border |
| 2 | Spending composition (6mo) | **1** | Only chart showing category *and* trend | Kept, accent border |
| 3 | Net worth — history | **1** | Only long-run "is this working" view | Kept, accent border |
| 4 | Liquid-balance forecast | **1** | Most actionable forward-looking chart | Kept, accent border |
| 5 | Month by month (table) | **1** | Fastest numeric glance; drill-down entry point | Kept |
| 6 | P&L vs target (5mo, clickable) | 2 | Line is redundant; the click-through isn't | Kept, now full width |
| 7 | Predicted income (6mo) | 2 | Useful, but rarely surprises for stable income | Kept |
| 8 | Expense breakdown + Income sources | 2 | Drill-down *output*, not a standalone view | **Income sources removed** (by request); Expense breakdown kept, full width |
| 9 | Cash flow (Sankey) | 3 | Flashy; flow is too simple to need it | **Removed** — `SankeyChart` class deleted (no other consumer) |
| 10 | Spending by tag | 3 | Third lens on a question #2 already answers | **Removed** — `backend.spend_by_tag` kept (has its own test, still pure/reusable) |
| 11 | Income vs Expenses (all months) | 3 | Decorative sibling of #6, no interaction | **Removed** |
| 12 | Plan vs actual | 3 | Dead unless bank import is configured | Kept — only remaining Tier-3 item; empty-state wording standardized |

## Trim executed

#9, #10, #11 were cut per the plan below, plus "Income sources" (half of #8)
was removed by explicit request while keeping "Expense breakdown." The page
went from 15 graphics to 10. #12 (Plan vs actual) was deliberately kept
despite being conditionally dead — cutting it wasn't requested, and it's
harmless once bank sync is configured.

Original plan, for reference — cut in this order for the least loss:
**#11 → #9 → #10 → #12** (only if bank sync stays unused) — none of these
lose a question Tier 1/2 don't already answer. Don't touch #6/#8 together —
cutting one breaks the drill-down
feature for the other.

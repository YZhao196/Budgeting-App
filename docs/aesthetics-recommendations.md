# Making the app more aesthetically pleasing

Grounded in the actual palette/tokens (`theme.py`), the current Analytics/
Overview/Subscriptions layouts, and this session's own screenshots — not
generic UI advice. Every item below cites the file/token responsible and
explains the *why*, in priority order. The app's flat, sharp, dark
"terminal/trading-desk" identity (stated in `PRODUCT.md`) is treated as a
constraint to work within, not a problem to fix — nothing here proposes
softening that identity into a generic rounded-corner SaaS look.

---

## 1. Chart category colors aren't stable — the same category can be a
## different color in different charts (highest-value fix)

**The problem:** Every chart that colors by category — the expense donut
(`main.py:818`), the spending-composition stacked bar (`main.py:609`,
`widgets.py:3798`), the Sankey ribbons (`widgets.py:4373`/`4398`) — assigns
color purely by **positional index**: `T.SERIES[i % len(T.SERIES)]`, where `i`
is that category's position in *that specific chart's own, independently
sorted list*. There is no stable category → color mapping anywhere in the
app. If "Rent" is the largest expense this month (donut sorts by amount, so
Rent lands at index 0 → sage green) but isn't the single largest across the
whole 6-month composition chart's own ranking, Rent could render as steel
blue there instead. A user trying to build "green dot = Rent" as a mental
model across the page can't — the mapping silently shifts chart to chart.

**Fix:** Derive each category's color from a stable key (e.g. a hash of the
category name, or an explicit `category → SERIES[i]` dict built once from the
full category list and reused by every chart) instead of from each chart's
local sort position. This is a pure-logic change — a small shared helper in
`backend.py` (e.g. `category_color(name) -> str`) that every chart-feeding
call site uses instead of computing its own `i % len(SERIES)`.

## 2. Three of the eight categorical colors are identical to functional
## colors used elsewhere (green/red/amber)

**The problem** (`theme.py:26-48`): `SERIES[0]` is `#5da876` — the *exact*
same hex as `GREEN` (income/positive). `SERIES[2]` is `#c8944a` — identical to
`AMBER` (warnings/due-soon). `SERIES[3]` is `#b86060` — identical to `RED`
(expense/negative). Everywhere else in this app, green means "good/income,"
red means "bad/expense," and amber means "warning/due soon" — that's a
deliberately disciplined, functional use of color per the file's own header
comment ("Functional colour for income/expenses; no gradients"). But the
categorical series breaks that discipline: if some arbitrary expense category
(say, "Household") lands on `SERIES[3]` in the donut chart, it renders in the
*exact* red the rest of the app uses to mean "you're over budget" or
"expense" — even though landing on that palette slot means nothing bad at
all. This directly undercuts the app's own color language.

**Fix:** Replace the 3 overlapping series colors with genuinely distinct
hues that don't collide with `GREEN`/`RED`/`AMBER` — the existing non-clashing
five (`#6b8fc4` steel blue, `#7a68a8` muted purple, `#4aacac` teal, `#c47a5a`
copper, `#8ab060` yellow-green) already prove the palette *can* stay muted and
desaturated without borrowing the functional hues. Pick 3 more in that same
family (candidates: a dusty rose distinct from `RED`, a muted gold distinct
from `AMBER`, a slate that reads as "neutral gray-blue" rather than
"income green").

## 3. Every card looks identical regardless of importance

**The problem:** `card()` (`main.py`) produces the same `BG_CARD` (`#1e1e1e`)
fill and the same `1px solid BORDER` outline for every single panel on the
page, whether it's the single most important chart (Budget vs actual) or the
least (Plan vs actual, which is often just an empty prompt). The
`analytics-graphics-review.md` companion doc identifies 5 "Tier 1" charts out
of 15 graphics on one page — but visually, all 15 present with identical
weight. The only hierarchy signal anywhere is font-size on the label above
each chart (12px muted vs 13px bold for a couple of headers) — a genuinely
weak hierarchy tool on its own (see the impeccable-design principle: strong
hierarchy wants 2-3 dimensions combined — size *and* weight *and* space, not
one alone).

**Fix, without abandoning the flat/sharp identity:**
- Give Tier-1 cards (Budget vs actual, Spending composition, Net worth,
  Liquid-balance forecast) a slightly brighter card fill or a subtle colored
  top border (the pattern already used on the Overview ledger cards —
  `border-top: 2px solid {accent}` — is sitting right there, unused on
  Analytics cards).
- Conversely, let Tier-3 cards (Sankey, Income vs Expenses line, Plan vs
  actual) sit on the plain `BORDER_SOFT` (`#202020`, already defined and used
  elsewhere as "subtle divider") instead of the standard `BORDER` — a
  quieter outline for quieter content.
- This is a few extra kwargs on `card()`, not a new component.

## 4. Uniform spacing rhythm across a very long page

**The problem:** Every gap on Analytics — between tile rows, between cards,
between paired-row charts — uses the same `T.GAP` (14px) or the page's own
`lay.setSpacing(14)`. With 15 stacked elements, uniform spacing means no
visual "paragraph breaks" — the eye has no cue for where one topic ends and
the next begins (this is the same principle the round-2 UX pass already
applied to Goals/History — `lay.setSpacing(14→22/20)` — worth extending here
too, more deliberately).

**Fix:** Keep tight spacing *within* a conceptually related pair (Liquid
forecast + Net worth already share a row; P&L trend + Income/Expenses
already share a row) but widen the gap *between* unrelated sections — e.g. a
visibly larger gap before "Cash flow" (a topic shift from budget-tracking to
flow-visualization) and before the donut/income-sources pair (a shift into
drill-down-detail territory). Concretely: introduce a second spacing
constant (e.g. `T.GAP_SECTION = 28`) used only at topic boundaries, alongside
the existing `T.GAP` for within-topic pairs.

## 5. No use of the sharp-top-border accent pattern outside the ledger cards

Related to #3: the Overview page's Incoming/Outgoing ledger cards use a 2px
colored top border as their *only* differentiator from a plain card, and it
reads well — it's a strong, on-brand hierarchy signal that costs nothing
stylistically (no gradient, no shadow, no radius) and is already proven in
this exact codebase. It's simply not reused anywhere else (Analytics,
Subscriptions, Goals all use the plain `card()` uniformly). Reusing it
selectively for "this is the most important card on this page" is the single
cheapest, most on-brand way to add hierarchy without touching the color
palette or introducing a new visual language.

## 6. Empty states are inconsistent in tone

Recent fixes gave several places a proper empty-state message (Budget vs
actual's "No category budgets set yet…", the Consumables tab's "No items
yet…"). Others still just render nothing or a single dim prompt line with no
visual weight at all (Plan vs actual's bank-import prompt, `main.py:736`).
Worth a pass to give every empty state the same visual treatment — dim
italic-weight text, consistent icon-or-none convention, and (where
applicable) a direct action link, matching the Budget-vs-actual pattern that
already exists as the reference implementation.

## 7. Chart legends never state units/scale explicitly — CORRECTED, already fine

**Original claim in this doc was wrong.** On review while implementing the
rest of this list, `DonutChart` (`widgets.py:4516`) already renders a
center-hole total via `center_top`/`center_sub` (confirmed live: the expense
donut shows `$2,411` / `"spent"` in its center) — this was missed on first
read. `StackedBarChart`'s `$3k`/`$2k` y-axis was correctly noted as already
good. No further action needed here; leaving this section in place (rather
than deleting it) as a record that the concern was checked and is already
handled, not skipped.

---

## What's already working well (keep doing this)

- **Disciplined, muted palette.** No neon, no gradients, no drop shadows —
  consistent with a "trading desk," not a consumer app. Don't chase trendy
  glassmorphism/shadows here; it would fight the app's own identity.
- **Vector line icons drawn as code** (`icons.py`) rather than bundled image
  assets — consistent weight/style across the whole sidebar, recolorable for
  hover/active states for free. This is a genuine strength, not something to
  change.
- **Functional color discipline** (green=income, red=expense, amber=warning)
  everywhere *except* the categorical series overlap flagged in #2 — the fix
  there is a narrow one, not a rethink of the whole system.
- **Sharp corners / zero radius everywhere.** Consistent, deliberate, and
  distinct from the generic-SaaS rounded-card look — worth explicitly keeping
  as new components get added, not something to "modernize" away.

## Priority order — status: all executed

1. **#2 (color collision)** — ✅ done. `theme.py` SERIES: the 3 colliding
   entries (identical to `GREEN`/`AMBER`/`RED`) replaced with 3 new muted,
   non-colliding hues. Verified: `T.GREEN/RED/AMBER not in T.SERIES`.
2. **#1 (stable category colors)** — ✅ done. Added `T.category_color(name)`
   (deterministic FNV-1a-style hash → stable `SERIES` slot, no process-seed
   randomization). Every category-coloring call site — the Analytics-Overview
   donut + legend, the per-tab `LedgerDetailPage` donut + legend, the
   spending-composition stacked bar (and its internal fallback default), and
   `SubscriptionTimeline`'s per-subscription marker color — now derives color
   from the category/subscription *name* instead of each chart's own local
   sort position.
3. **#3 + #5 (hierarchy via top-border accent)** — ✅ done. `card()` gained an
   `accent=` param (2px colored top border); applied to the 4 Tier-1 charts
   (Budget vs actual, Spending composition, Net worth, Liquid-balance
   forecast). Everything else keeps the plain quiet border by default — no
   separate "quiet" variant needed since that was already the default.
4. **#4 (spacing rhythm)** — ✅ done. Added `T.GAP_SECTION = 28`; three extra
   `addSpacing()` breaks inserted at genuine topic boundaries on the (now
   shorter, post-trim) Analytics page: before the forecast/net-worth row,
   before the predicted-income/plan-vs-actual row, and before the drill-down
   donut section.
5. **#6, #7** — ✅ done, with a correction. #6: standardized empty-state
   wording/style ("No X yet — click Y to Z, then this happens") for Plan vs
   actual and the Consumables tab, both now `T.TEXT_DIM, 11` + `setWordWrap`.
   #7 turned out to already be handled — `DonutChart` already renders a
   center-hole total (confirmed live: `$2,411` / `"spent"`); the doc's
   original claim that it lacked one was wrong and has been corrected above
   rather than left standing.

# Full review — executed per `review-methodology.md`, using Oct/Nov 2026 real data

This is `docs/review-methodology.md` actually run, start to finish, using the
68 real-shaped transactions imported from the user's October/November 2026
spending lists as live test data (see `docs/real-data-import-test.md` for the
import step itself). All six dimensions, in order, each following its §2
method, each finding in the §3 format (observation → location → why → fix or
decision), tiered per §3's instruction not to leave a flat list.

---

## §0 — Yardstick check

`PRODUCT.md` was re-read fresh, not from memory, per the methodology's own
first instruction. **Flag:** the working copy currently differs from the last
committed version — the "Platform" and "Anti-references" sections are
missing and "Brand Personality" is shortened, and this wasn't changed by any
Claude session. This review proceeds against the **current file contents**
(per the methodology's own instruction: "review against the new version"),
but the discrepancy is still unresolved — see the standing question from the
previous turn. Nothing below depends on the missing sections' specific
wording, so the review isn't blocked by it.

The two load-bearing lines from `PRODUCT.md` that this review keeps
returning to:
- *"Success is a single glance at the Overview page answering 'am I on
  track' without digging."*
- *"The plan and the bank statement live in the same tool and are held to
  the same standard... this one keeps both live at once."*

Finding 1 below is a direct, quantified test of both sentences at once.

---

## Findings

### CRITICAL

#### Finding 1 — Overview's headline number is plan-only; bank reality never reaches it — ✅ FIXED (option b)
**Observed:** `backend.income_total` / `expense_total` / `pnl` — the
functions behind every number on the Overview page and most of Analytics'
tiles — operate exclusively on `doc.get("income"/"expenses")`, the recurring
*plan* tree. None of them read `dm.transactions()`. Confirmed by hand
computation against the imported October 2026 data:

```
Overview shows:              income $5,880.00  expense $2,410.99  P&L +$3,469.01
Real bank-confirmed spend:                      expense $3,716.03  (35 transactions)
Real P&L if actual spend were used instead:                        P&L +$2,163.97
Gap between the number on screen and reality:                       $1,305.04
```

**Location:** `backend.py:71-151` (`active_total`, `income_total`,
`expense_total`, `pnl`); consumed directly by `OverviewPage`
(`main.py`) and the Analytics tile row. Also confirmed for
`category_series` (`backend.py:1208`, feeds "Spending composition") and
`_show_breakdown`'s donut (`main.py`, feeds "Expense breakdown") — both also
read only the plan tree, never transactions.

**Why it matters (§0):** this is not a rounding error, it's the single
number `PRODUCT.md` names as the entire point of the app ("a single glance...
without digging") being silently wrong by 27% of the household's actual
spend for the month, with the correct figure visible *only* by opening
Analytics and reading one small card ("Plan vs actual") near the bottom of a
long page — not by anything on Overview itself. It also directly contradicts
"plan and reality... held to the same standard" — reality doesn't reach the
standard of being shown at all outside that one card.

**Fix (architectural, not a quick patch):** either (a) have Overview's
headline P&L prefer bank-reconciled actuals for any month where transactions
exist, falling back to plan for months with none, or (b) keep the plan
number primary but add an explicit, visible delta ("bank says $X actual —
$1,305 more than planned") directly on Overview, not buried in Analytics.
Option (a) is the more literal reading of "plan and reality are peers";
option (b) is smaller and preserves the "plan projects forward" framing
`PRODUCT.md` also states. This is a product decision, not a bug fix — flagged
here rather than silently picked.

#### Finding 2 — No per-transaction categorization UI exists anywhere — ✅ FIXED
**Observed:** `ItemStore.set_transaction_category(txn_id, category)`
(`datamanagement.py:963`) is fully implemented but has **zero call sites**
in `main.py` or `widgets.py` (confirmed by grep). Every UI use of
`dm.transactions()` is an aggregate — a count, a sum, a subscription-pattern
scan — never an individual, clickable row. The only categorization lever
exposed to the user is authoring a free-text substring rule in Settings
(`main.py:1403`), with no view of which raw transaction descriptions are
actually uncategorized and no autocomplete against existing category names.

**Why it matters:** combined with the previous test's Finding 1 (79% of
realistic transactions get no category), there is no practical path to ever
closing that gap for the transactions a blind rule-guess doesn't happen to
match — the user can see *that* 54 transactions are uncategorized (Settings'
status line) but not *which* ones, so writing a correct rule means guessing
at description text that was never shown.

**Fix:** a transaction list view (even a simple one — date, description,
amount, category dropdown) reachable from Settings' import card would close
this entirely, and would let `set_transaction_category` finally be called
from somewhere.

---

### HIGH

#### Finding 3 — Rule categories must exactly string-match an expense name, silently, with no validation — ✅ FIXED
**Observed:** `budget_report` reconciles a transaction's `category` string
against expense-definition `name` fields by exact match. A rule mapping
"woolworths" → "Groceries" produces real, correct `actual` spend under a
"Groceries" row — but since no expense *definition* is named "Groceries" in
the recurring ledger, that row's `planned` figure is permanently `$0`,
making it read as "100% over budget" no matter how small the spend, forever,
by construction rather than by any real overspend. Confirmed live: Groceries,
Transport, Food & Dining, Shopping, and Health & Fitness (categories that
exist as real, expected monthly costs) all show `planned=$0.00` in both
October and November's reconciliation.

**Location:** `datamanagement.py`'s `categorise()`/rule application, and
the free-text `QLineEdit` at `main.py:1403` with placeholder text
`"category (e.g. Groceries)"` — the placeholder itself invites exactly the
mismatch, since "Groceries" isn't (and, per the recurring-ledger model,
structurally can't easily be) an expense definition name unless the user
independently also creates a matching recurring "Groceries" expense item.

**Why it matters:** a category showing "$0 planned, over budget" every
single month for a real, ordinary expense isn't a signal of anything —
it's structural noise that will train the user to ignore the "over budget"
signal generally, weakening it exactly where it should be trusted.

**Fix:** when authoring a rule, either populate the category field with a
dropdown/autocomplete of existing expense-definition names (steering the
user toward alignment), or treat "no matching plan" as its own explicit
state in the reconciliation UI (e.g. "not budgeted" rather than "$0 over"),
distinct from a real overspend against a real plan.

#### Finding 4 — Nothing on Overview signals that reality has diverged from plan — ✅ FIXED (same change as Finding 1)
**Observed:** Following directly from Finding 1 — there is no badge, color
shift, or notice anywhere on Overview indicating bank-confirmed spend
differs from the plan, even at the $1,305/month scale measured here.

**Why it matters:** per `PRODUCT.md`'s "calm under bad news... reported
factually" principle, the app is clearly designed to *show* bad news
plainly when it has the data to show it (overdue bills render in red with a
label, negative net worth is stated outright) — this is a case where the
data exists (Analytics computes it every time `set_context` runs) but
Overview, specifically, never sees it.

**Fix:** same as Finding 1 — this is the same underlying gap, restated from
the discoverability angle rather than the correctness angle.

---

### MEDIUM (carried over from the prior import test, reconfirmed here)

#### Finding 5 — Weekly real cadence vs. monthly-modeled ideal produces a false variance — NOT CODE-CHANGED (by design)
Unchanged from `docs/real-data-import-test.md` Finding 4: Rent's $2,000/mo
model against $450/week real payments shows a false "+$250 over" in
5-Monday October and a false "-$200 under" in 4-Monday November. Not a code
bug — a recurrence-cadence modeling choice, restated here because it's the
same class of problem as Finding 3 (a reconciliation reading as a real
signal when it's actually a modeling artifact).

#### Finding 6 — "Might've forgotten" false-positives on an already-tracked expense — ✅ FIXED
Unchanged from the prior test's Finding 3: `SubscriptionsPage
._forgotten_section` (`main.py:2290`) excludes only `all_subscriptions()`
(subscription-flagged/shared items), not every tracked expense, so Rent gets
re-flagged as forgotten despite being fully modeled and correctly
categorized every month.

---

### Aesthetics (dimension E) — one finding, real-data-specific

#### Finding 7 — The uncategorized count doesn't get functional color despite representing a real, sizable gap — ✅ FIXED
**Observed:** Settings' import status (`main.py:1674`,
`f"color:{T.TEXT_MUTED}"`) renders "54 uncategorised" in the same neutral
gray whether the count is 1 or 54 (79% of imported transactions, this
test). `PRODUCT.md`'s "Functional color only" principle states color always
encodes a real state, paired with label/position — an uncategorized count
this large *is* a real state (it's the direct cause of Finding 3's
structural noise), yet gets no visual distinction from a healthy count.

**Fix:** scale the status label's color with the uncategorized ratio (e.g.
amber past some threshold, consistent with how overdue bills or
over-budget categories already get amber/red treatment elsewhere) rather
than a flat neutral gray regardless of severity.

---

### Positive findings (§3 — record what's working, not only what's broken)

- **CSV import mechanics are solid.** All 68 transactions across two
  differently-formatted source files parsed and imported with zero
  duplicates and zero manual massaging — the flexible column-sniffing in
  `importers.py` worked on real data on the first attempt.
- **`detect_subscriptions` correctly caught a genuine gap** — "Weekly Gym
  Membership" ($15 × 8 occurrences) — with no tuning, on data it had never
  seen.
- **Uncategorized spend is surfaced, not hidden.** `budget_report` includes
  an explicit "Uncategorised" row with its real dollar total rather than
  silently excluding it from the reconciliation total — this is the one
  place bank reality *does* show up unmissably, and it should be the model
  for how Finding 1's fix surfaces the larger gap.

---

## Dimension coverage

| Dimension | Covered by | Method used |
|---|---|---|
| A. Correctness | Findings 1, 3, 5 | Hand-computed Oct P&L against real bank totals; verified Rent's 5-Monday variance by hand |
| B. Practicality | Findings 2, 6 | Grepped for transaction-categorization UI call sites; walked the real reconciliation flow end-to-end |
| C. UX | Finding 4 | Traced what Overview does and doesn't surface, against `PRODUCT.md`'s stated calm-under-bad-news principle |
| D. Information architecture | Finding 1 (supporting) | Confirmed "Spending composition" and "Expense breakdown" also read plan-only, same root cause as Overview |
| E. Aesthetics | Finding 7 | Checked the import-status label's color against severity, per functional-color principle |
| F. Technical health | Finding 2 | Grepped `set_transaction_category` across `main.py`/`widgets.py` for call sites — found none |

Every dimension in the methodology was exercised against the same live,
real dataset rather than six separate synthetic passes — which is itself a
confirmation that the methodology's dimensions aren't independent in
practice: Finding 1 (correctness) turned out to be the same underlying gap
as Finding 4 (UX) and a contributing cause of Finding 7 (aesthetics), which
the six-dimension structure made easy to trace back to one root cause
instead of recording as three unrelated complaints.

---

## Implementation status

6 of 7 findings fixed; verified against the same live Oct/Nov 2026 dataset
used to find them (114+4 pytest cases pass throughout; every fix also
re-checked by hand computation or headless capture, not just "code looks
right"):

- **Finding 1 + 4** (Overview shows no reality signal) — took **option (b)**
  from the original writeup: the plan number stays primary, and
  `SummaryCard` (`widgets.py`) gained a "Bank says" banner that appears only
  for months with imported transactions, showing bank-confirmed spend and
  the delta from plan, colour-coded (red = more than planned, green =
  less). Verified: shows *"$3,716 spent ($1,305 more than planned)"* for
  October, red; correctly hidden for July (no transactions that month).
  Option (a) — rewiring `income_total`/`expense_total` themselves — was
  rejected as riskier than needed: it would change behaviour for every
  consumer of those functions (History, Goals, Predicted Income, all of
  Analytics), not just Overview, for a problem a visible delta already
  solves without touching well-tested core math.
- **Finding 2** (no per-transaction categorisation UI) — new
  `TransactionReviewDialog` (`widgets.py`), reachable via a "Review
  transactions…" button next to Import/Clear in Settings. Lists every
  transaction (uncategorised first), each with an editable, autocompleted
  category field; saving calls the previously-dead
  `ItemStore.set_transaction_category` for every changed row. Verified
  end-to-end headless: built all 68 rows, edited one, saved, confirmed the
  uncategorised count actually dropped and the Settings status text/colour
  updated live.
- **Finding 3** (rules must exact-match, no validation, "over" is a false
  signal for unbudgeted categories) — two changes: (a) the rule-authoring
  category field (`main.py`) now has a `QCompleter` populated from
  `ItemStore.expense_names()` (new public accessor, wrapping the
  already-existing private `_expense_names()`), refreshed whenever rules
  change; (b) "Plan vs actual" rows with `planned == 0` now read "not
  budgeted" instead of "$X over" — verified live: Entertainment, Groceries,
  and the Uncategorised bucket all correctly show "not budgeted" for
  October instead of a fabricated overspend figure.
- **Finding 5** (weekly Rent vs monthly model) — **intentionally left
  uncoded.** The original finding explicitly called this a modeling choice
  for the data's owner to make (model Rent's recurrence as weekly if that's
  the real cadence), not a code defect — changing the demo data's own Rent
  recurrence here would just be picking a different demo assumption, not
  fixing anything. Documented, not silently applied.
- **Finding 6** (forgotten-subscription false positive on Rent) — `main.py`'s
  `_forgotten_section` now excludes every tracked expense name
  (`ItemStore.expense_names()`), not just subscription-flagged items.
  Verified: Rent no longer appears in the "might've forgotten" list;
  "Weekly Gym Membership" (the genuine catch) still does.
- **Finding 7** (uncategorised count never gets warning colour) — Settings'
  import-status label now turns amber once the uncategorised share reaches
  30% (`SettingsPage._UNCATEGORISED_WARN_RATIO`), instead of a flat neutral
  grey regardless of severity. Verified: renders amber at the current
  68-transaction/54-uncategorised (79%) state.

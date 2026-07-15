# Real-data import test — October/November 2026 spending

A practicality test per `docs/review-methodology.md` §2.B ("walk one real
month end-to-end, don't sample screens"), using two realistic transaction
lists supplied by the user (68 real-shaped transactions across two months:
groceries, transport, dining, gym, rent, utilities, entertainment,
shopping). Converted to a bank-export-shaped CSV (`Date,Description,Amount`,
no category column — a real bank export wouldn't hand the app pre-sorted
categories) and run through the actual import pipeline
(`importers.parse_file` → `ItemStore.import_transactions`), not a mock. This
is exactly the "Connect bank accounts" flow a real user would use.

**Result: all 68 imported cleanly, 0 duplicates, 0 parse failures.** The CSV
importer's flexible column-sniffing worked on the first try with no
massaging. The findings below are about what happens *after* import, not
the import mechanism itself.

---

## Finding 1 — Categorization coverage is low on realistic data (HIGH)

**Observed:** 14/68 transactions (21%) auto-categorized; by dollar value,
36% of total spend (`$2,499.63` of `$6,873.61` across both months) landed in
"Uncategorised." Confirmed live in Settings: *"68 transactions imported ·
54 uncategorised."*

**Cause:** `ItemStore.categorise()` (`datamanagement.py`, called from
`import_transactions`) only matches two things: (a) an explicit user-created
rule (`rules()`, substring match against the description), or (b) an
existing expense *definition name* appearing verbatim as a substring of the
description. Every categorized transaction in this test hit one of those two
paths exactly: "Woolworths" (a rule) and "Netflix" (both a rule and an exact
name match), plus "Rent" and "Electric" matching as substrings of "Weekly
**Rent** Payment" and "Monthly **Electric**ity Bill." Everything else —
"Lunch - Local Cafe," "Train Fare," "Weekly Gym Membership," "Fuel -
Caltex," "Cinema Tickets & Popcorn" — has no rule and no matching category
name, so it falls through with no category at all.

**Why it matters (§0):** `PRODUCT.md`'s stated success condition is "a
single glance at Overview answering 'am I on track'... enough density
elsewhere to trust the number when it says no." A budget-vs-actual view that
silently excludes a third of real spending from every category comparison
can't be trusted at a glance — it looks like categories are on-budget when
in fact spend simply isn't being counted there.

**Fix (not yet applied — a design decision, not a quick patch):**
- **Minimal:** ship a broader *default* rule set covering common category
  keywords ("coffee"/"cafe"/"lunch" → Food & Dining, "fuel"/"petrol" →
  Transport, "gym"/"fitness" → Health & Fitness), seeded once, editable like
  any other rule.
- **Better, reuses an existing pattern:** `detect_subscriptions` already
  groups transactions by recurring merchant pattern for the "Might've
  forgotten" card (Finding 2 shows this works well). A parallel "Suggest
  rules from uncategorised transactions" flow — group uncategorized
  transactions by recurring description pattern, propose a rule per group,
  let the user approve in bulk — would directly close this gap using
  machinery that's already proven to work on this exact data.

---

## Finding 2 — "Might've forgotten" correctly caught a real untracked pattern (positive)

**Observed:** `detect_subscriptions` correctly identified "Weekly Gym
Membership" ($15 × 8 occurrences across both months) as a recurring pattern
with no matching tracked item — exactly the intended behavior, on real
(if synthetic-realistic) data, with no tuning needed.

**Why it matters:** this is the feature working as designed; recorded here
so it isn't lost among the things that need fixing — per
`review-methodology.md` §3, a review should note what's already working,
not just what's broken.

---

## Finding 3 — Same feature false-positives on an already-tracked expense (MEDIUM)

**Observed:** The same "Might've forgotten" pass also flagged "Weekly Rent
Payment" ($450 × 9 occurrences) as untracked — even though Rent is a fully
modeled, correctly-categorized recurring expense in the ledger (it's the
single most successfully-categorized item in Finding 1).

**Cause:** `SubscriptionsPage._forgotten_section` (`main.py:2287-2293`)
builds its exclusion list from `self.dm.all_subscriptions()` only — which
returns items flagged `subscription=True` or `shared`
(`datamanagement.py`), not *every* tracked expense definition. Rent is a
plain recurring expense, never flagged as "my subscription," so it's never
in the exclusion set and gets re-flagged every time it appears in an import.

**Fix:** widen the `tracked` list at `main.py:2290` to include every expense
definition's name (`self.dm.items()`, filtered to type="expense"), not just
`all_subscriptions()`. The "Might've forgotten" feature's actual intent is
"a recurring bank pattern with nothing already accounting for it" — a plain
tracked expense already accounts for it just as much as a flagged
subscription does.

---

## Finding 4 — Weekly real cadence vs. monthly-modeled ideal produces a false variance (MEDIUM, modeling choice not a bug)

**Observed:** Rent's recurring ledger item models a flat $2,000/month ideal.
Real bank data pays weekly at $450: October 2026 has 5 Mondays → actual
$2,250 (12.5% over); November 2026 has 4 → actual $1,800 (10% under).
Neither reflects an actual budget problem — it's an artifact of comparing a
monthly-granularity model against a weekly real payment cadence, and it will
recur every month that has 5 of whichever weekday rent is paid on (roughly
4 months a year for any given weekday).

**Why it matters:** per `review-methodology.md` §1.A (correctness), a
reconciliation that reports a false "$250 over" isn't just imprecise, it
actively erodes trust in the one number `PRODUCT.md` says has to be
trustworthy at a glance.

**This is not a code bug** — `budget_report`'s math is correct given its
inputs. It's a modeling-choice finding: if a recurring expense's *actual*
cash-flow cadence is weekly, model it as `{"type":"interval","every":1,
"unit":"week"}` rather than monthly, so the reconciliation compares
like-for-like cadence instead of a monthly average against a variable-week
actual. Worth a general callout in the app (or its docs) that recurrence
modeling should match real payment cadence, not just "close enough."

---

## Finding 5 — Uncategorized spend is surfaced, not hidden (positive)

**Observed:** `budget_report`'s rows include an explicit `"Uncategorised"`
entry with its real dollar total (Oct: $1,249.44, Nov: $1,250.19), and the
Analytics "Plan vs actual" card renders it as an ordinary row like any
category — it isn't silently dropped from the reconciliation.

**Why it matters:** this directly mitigates the severity of Finding 1 — a
user looking at "Plan vs actual" (not just "Budget vs actual," which needs
an `ideal` to show anything at all) *would* see a large, named
"Uncategorised" line and know spend is going untracked, rather than the app
quietly under-reporting total spend with no visible signal. Worth
preserving this behavior explicitly if Finding 1's fix is ever implemented
as a UI change — the "everything uncategorized is visible" property matters
independent of how good auto-categorization gets.

---

## What was and wasn't verified

- **Verified live and by direct computation:** import counts, categorization
  rate, `detect_subscriptions` output (both the correct catch and the false
  positive), `budget_report` planned/actual/uncategorized figures for both
  months, Settings' import-status string.
- **Verified by direct computation only (not a fresh screenshot of this
  exact reconciliation row rendering):** the "Plan vs actual" card's
  per-row rendering of the Uncategorised line — the rendering code path
  itself was already screenshot-verified earlier this session with
  synthetic data; only the *data feeding it* is new here.
- **Not tested:** OFX import (only CSV was exercised, since that's the
  format the source data naturally converts to); the "Clear imported"
  button's interaction with a large (68-row) transaction set; whether
  `recategorise_all()` (triggered by adding a new rule) performs acceptably
  at this data volume (68 rows is too small to say anything about scaling).

## Data disposition

The 68 transactions from both files are imported into the live app
(`data/items.json`'s `transactions` list) — left in place, not reverted,
since the request was to use this data to test the app, and leaving it
in place is what makes the findings above reproducible. The two source
`.txt` files were only read, never modified or copied into the repo.

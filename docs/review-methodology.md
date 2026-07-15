# How to review this app — process, dimensions, and method

A process document, not a critique. It doesn't judge the app; it lays out
*how* to judge it — what to look at, in what order, with what tools, and what
a usable finding looks like — so a review produces the same quality of output
whether it's run by a future Claude session or by the app's own author.
Everything here is grounded in this specific app (`PRODUCT.md`, the actual
code, and the review docs already produced this session), not generic
"UX audit" boilerplate.

---

## 0. Read the yardstick before reviewing anything

Every review starts by re-reading `PRODUCT.md` — not from memory, from the
file, since it can change. It defines the only correct measure of "good" for
this app, and that measure is unusual enough to state plainly:

- **One user, not a market.** `PRODUCT.md`'s "Users" section: *"Not built for
  distribution; this is a personal tool used directly by its own author."*
  A finding like "this would confuse new users" is close to meaningless here
  — there are no new users, ever. The only question that matters is whether
  it works for the one person who uses it, at their own desk, regularly.
- **The stated success condition is explicit and testable:** *"a single
  glance at the Overview page answering 'am I on track' without digging."*
  Any review of Overview should be checked directly against this sentence —
  not against a general "is this a good dashboard" instinct.
- **Density is a deliberate feature, not a defect to fix.** A finding that
  amounts to "there's a lot going on here, simplify it" is only valid if it's
  also true that the density isn't earning its keep (see §3, Information
  Architecture) — density alone is not a problem per this app's own brand
  personality ("dense rather than simplified... the reference point is a
  terminal or trading-desk tool").
- **Plan and reality are peers.** Any review that treats the bank-reconciled
  view as secondary polish, or the recurring-ledger forecast as the "basic"
  mode, is measuring the app wrong — `PRODUCT.md` explicitly rejects that
  framing.
- **Anti-references name what "better" is not.** Mint/YNAB/Monarch's rounded,
  colorful, friendly style is explicitly out of scope as a direction — a
  recommendation to "soften" the visual language contradicts the brand brief
  on its face and should be rejected before it's even investigated.

If a review disagrees with something `PRODUCT.md` states, that's a
conversation to have with the app's author directly — update the brief, then
review against the new version. Don't quietly review against a different,
unstated standard.

---

## 1. The six review dimensions

Every review covers some subset of these; a full review covers all six. Each
has its own method in §2.

### A. Correctness & data integrity
Does the app compute the right numbers? This is the dimension with the
lowest tolerance for "close enough" — a budgeting tool that's aesthetically
flawless but silently miscalculates a balance is worse than an ugly one that
doesn't. Correctness bugs found and fixed this session (for calibration on
severity): the `ProgressBar` red-overrun math that painted a *winning* month
solid red; a money-entry field that spliced typed digits into a prefilled
`$0.00` instead of replacing it, silently producing `$2000` from a typed
`200`; a shared-subscription's stored `amount` needing to be the *gross*
total, not the payer's net share, or the owner's cost silently comes out
wrong.

### B. Practicality / real-workflow fit
Not "is this usable" in the abstract — "does this fit how the one actual
user actually uses money software, day to day, for months at a time."
Distinct sub-questions:
- **Entry friction**: how many clicks/fields to record something that
  happens often (a new expense, a bill payment, a subscription change)?
  Something done weekly can tolerate far less friction than something done
  once a year.
- **Maintenance burden**: does the app requires upkeep to stay trustworthy
  (re-categorizing transactions, re-entering budgets each month, manually
  reconciling)? Does upkeep grow linearly with data, or does it compound?
- **Recovery from absence**: if the user doesn't open the app for a month,
  is catching back up cheap, or does staleness compound into distrust of the
  numbers?
- **Failure mode when data is incomplete**: what does the app show when a
  budget isn't set, an account isn't added, a bank import hasn't happened?
  (This is where several of this session's fixes lived — a category with no
  budget rendering as a false "over budget" red bar, an Account search result
  silently doing nothing because its target page key didn't exist.)

### C. UX & interaction quality
Does driving the app feel the way `PRODUCT.md`'s brand personality intends —
precise, dense, no wasted motion — or does it fight the user? This dimension
is best caught by *using* the app as a real session, not by reading the code
(code review misses timing, focus behavior, and whether an affordance is
discoverable). See §2.C for the concrete method used this session.

### D. Information architecture — does each element earn its place
For any page with more than a small handful of things on it (Analytics is
the extreme case — it went from 15 stacked graphics to 10 this session),
each element needs an answer to: *what question does this answer, and is it
the only place that question is answered?* An element that restates another
element in a different chart type is a tax on scanning, not added
information. `docs/analytics-graphics-review.md` is the worked example of
this dimension in practice — every graphic tiered (essential / secondary /
redundant) with the reasoning written down, not just a verdict.

### E. Aesthetics & brand consistency
Distinct from UX — this is about whether the *visual system* (color,
spacing, type, hierarchy) is applied with the discipline `PRODUCT.md`
describes, not whether interactions work. Concretely: does color ever carry
meaning it shouldn't (the SERIES/functional-color collision found this
session); does every element get equal visual weight regardless of actual
importance; is spacing rhythm doing any work or is it uniform padding
everywhere; does typography stay legible at the small sizes this density
requires. `docs/aesthetics-recommendations.md` is the worked example.

### F. Technical health
Not user-facing, but it gates how safely the other five dimensions can keep
being acted on. Concretely, for this codebase:
- **Test coverage of pure logic.** `backend.py`/`datamanagement.py` functions
  should be tested independently of the UI (`tests/test_backend.py`,
  `tests/test_importers.py` — currently 118 passing cases). New pure
  functions (like this session's `tracker_cost_per_use` family) should ship
  with tests in the same commit, not after.
  UI code (`main.py`, `widgets.py`) is not unit-tested — it's verified via
  headless screenshot capture (`python main.py --shot <path> --page <name>`)
  and hands-on driving instead. Know which verification method a given
  change needs before claiming it's "tested."
- **Dead code after a feature changes.** When a UI consumer is removed (this
  session: the Sankey chart, the "Income sources" card), check whether the
  widget class or backend function it used becomes orphaned — delete the
  class if nothing else uses it, but check for an independent test first
  (`spend_by_tag`/`cashflow_links` were kept because they're independently
  tested, reusable pure logic, not because they were hard to delete).
  Grep for the symbol name across `main.py`/`widgets.py`/`tests/` before
  deciding either way.
- **Migration debt.** The app carries a legacy `DataManager`/`data/months/*`
  code path from before the flat `ItemStore` model; confirmed this session
  that `data/months/*.json` no longer influences anything the running app
  reads (`ItemStore.load_month` derives everything from the flat store).
  Worth periodically re-confirming nothing has quietly started depending on
  it again, and worth a deliberate decision on whether to delete it outright
  rather than let it linger indefinitely as read-only history.
- **Local demo/dev data hygiene.** `data/*.json` is gitignored — nothing
  protects it from being overwritten by a careless verification script that
  runs `datamanagement.ItemStore()` against the real path instead of an
  isolated fixture (this happened this session; the demo dataset had to be
  reconstructed from screenshots). Any review or future session that runs
  verification scripts against live data should isolate them (`tmp_path` +
  `monkeypatch.setattr` on the relevant `*_FILE` constant, or the
  `store.save = lambda: None` pattern already used in
  `tests/test_backend.py::_store_with`) rather than touching the real files.

---

## 2. Method — how to actually do each

### A. Correctness — read the formula, then verify it against a hand-computed example
Don't just read the code and nod. Pick a concrete example, compute the
expected answer by hand (or in a throwaway Python one-liner), then run the
actual function and diff. This session's pattern for the tracker feature:
computed cost-per-use manually for a "30mL bottle, 5mL/use, $24" example
($4.00/use), then called `backend.tracker_cost_per_use()` on the same input
and confirmed the match — this is how the Spotify-Family gross-vs-net amount
bug was caught (a plausible-looking dialog result produced a number that
didn't match hand arithmetic). For anything touching money, this hand-check
is not optional.

### B. Practicality — walk one real month end-to-end, don't sample screens
Pick a plausible real scenario (e.g. "record this month's rent, an unplanned
grocery run, mark a bill paid, check if a goal is still on track") and
execute every step through the actual UI, timing the friction, rather than
opening each page once and eyeballing it. Practicality bugs hide in
*sequences* (e.g. add item → Tab → does focus land somewhere useful) that a
single-page review won't surface.

### C. UX — drive the live app, don't just read the widget code
Reading `widgets.py` tells you what a component is *supposed* to do; it
won't tell you that a dialog spawns off-screen when launched from a
top-right button, or that a modal blocks silently with no visible dialog in
a screenshot taken half a second too early. This session's method:
1. Launch the real app (`python main.py`, not a mock) via computer-use or an
   equivalent on-screen driving tool, so real timing/focus/paint behavior is
   observed, not simulated.
2. Perform real tasks — add, edit, delete, navigate, search, resize — the
   way an actual session would, not a scripted happy path.
3. Where something looks wrong, drop into the code to find the *cause*, not
   just describe the symptom — a finding like "off-screen dialogs" is only
   actionable once it's `place_near_cursor`'s missing screen-bounds clamp.
4. Cross-check surprising claims against a fresh headless capture
   (`--shot`) before writing them down — this session corrected an earlier
   claim that search was a "dead end" after re-reading the wiring and
   re-testing; a wrong finding that ships is worse than a missing one.

### D. Information architecture — inventory first, judge second
Don't rely on impression ("this page feels busy"). List every distinct
element on the page by name and file location, then for each one write one
sentence: *what question does this answer?* Once every element has that
sentence, redundancy becomes visible by comparison — two elements whose
sentences are near-identical are a signal, not a feeling. This is exactly
the method behind `analytics-graphics-review.md`'s tiering.

### E. Aesthetics — check the palette and spacing tokens against the code, not the screenshot alone
A screenshot shows how colors *look*; it won't show that two colors are
byte-identical hex values serving different semantic purposes until you grep
the constants file. Concretely: diff every color token
(`theme.py`) against every other one for exact or near-exact duplicates
across different *semantic* categories (functional vs. categorical); grep
chart color-assignment call sites for whether they key off a stable name or
a transient index/position. Spacing rhythm is checked the same way — grep
every `setSpacing()`/`addSpacing()` call on the page in question and look
for "is every gap the same number," which a screenshot alone makes hard to
notice consciously even though it's easy to feel.

### F. Technical health — grep before you delete, run the whole suite before you claim done
Before removing a class or function: `grep -rn <symbol> main.py widgets.py
backend.py datamanagement.py tests/` — check both other call sites and
existing tests. Before calling any change complete: `python -m pytest -q`
for the full suite (not just the new tests), plus a headless `--shot`
capture of every page touched, since pytest doesn't cover `main.py`/
`widgets.py` UI code at all.

---

## 3. Output standard — what a finding should look like

A finding is not done until it has all four of these, in this order:

1. **What's observed** — concrete, from actually running the app or reading
   the actual code, never "probably" or "might."
2. **Where it lives** — file and line/function, so it's actionable without a
   second research pass.
3. **Why it matters, relative to §0** — tie it back to the actual product
   goal, not a generic UX principle. "This chart is redundant" is weaker
   than "this chart restates the same question `Spending composition`
   already answers, per the one-sentence test in §2.D."
4. **A concrete fix or an explicit decision to leave it** — either a specific
   code change, or a stated reason it's being left alone (e.g. `spend_by_tag`
   was kept despite its UI going away, because it's independently tested and
   might be reused). "Worth reconsidering" without a proposed direction is
   an incomplete finding — every one of this session's docs that used that
   phrase came back to it later with an actual decision.

Findings should be tiered (essential/secondary/low-value, or
critical/moderate/cosmetic) rather than presented as a flat list — a review
that doesn't rank its own findings pushes the prioritization work onto
whoever reads it, defeating the point of doing the review at all.

---

## 4. When to run a review

- **After any feature ships**, review the specific surfaces it touched (all
  six dimensions, scoped to that feature) before moving on — this is how
  each fix this session was verified before the next was started, rather
  than batching verification at the end.
- **Before a build/release** (`build.bat`), at minimum re-run the full test
  suite and a hands-on pass of anything changed since the last build — a
  stale `dist/Budget.exe` with unverified changes defeats the point of
  packaging it.
- **Periodically, even with no pending change** — practicality and IA drift
  over time as data accumulates (a page that was appropriately dense at 3
  months of history may not be at 18), and a scheduled re-read of `PRODUCT.md`
  against the current app catches drift that no single feature review would
  trigger on its own.
- **On return after time away** — the "recovery from absence" question in
  §1.B applies to reviewing the app just as much as using it; a fresh look
  after a gap tends to surface friction a continuously-familiar eye stops
  noticing.

---

## Appendix — quick checklist

- [ ] Re-read `PRODUCT.md` in full, not from memory.
- [ ] Correctness: pick one real number, hand-compute it, diff against the
      app's answer.
- [ ] Practicality: walk one real end-to-end month through the actual UI.
- [ ] UX: drive the live app on-screen; don't review from code alone.
- [ ] IA: inventory every element on the page in question; one sentence
      each on what question it answers; compare for redundancy.
- [ ] Aesthetics: diff color tokens for cross-semantic collisions; grep
      spacing calls for uniform-everywhere gaps.
- [ ] Technical health: grep before deleting; full `pytest -q` and a
      `--shot` capture of every touched page before calling anything done.
- [ ] Every finding has: observation, location, why (tied to `PRODUCT.md`),
      and a fix or an explicit decision to leave it.
- [ ] Findings are tiered, not a flat list.

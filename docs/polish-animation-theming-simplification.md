# Animations, polish, theming, and simplification — a practical guide

How to make this app more pleasant and effective to look at and use, without
drifting away from what it's actually supposed to be. Every recommendation
below is grounded in the current code (`theme.py`, `widgets.py`, `main.py`)
and checked against `PRODUCT.md` before being written down — several ideas
that would be standard advice for a generic app are flagged as **don't do
this here** specifically because they'd fight the brand brief. Read §0
before anything else; it's the filter every other section was run through.

---

## 0. The constraint every recommendation below respects

`PRODUCT.md` is explicit and unusually opinionated for a personal project:
*"dense rather than simplified... the reference point is a terminal or
trading-desk tool"*; *"no gradients, no soft shadows, no rounded corners, no
decorative color"*; anti-references explicitly name Mint/YNAB/Monarch's
rounded, friendly, colorful style as **not** the direction. `theme.py`
backs this up in code: `RADIUS = 0` globally, a strictly functional color
set (green/red/amber only ever mean income/expense/warning), flat panels
with 1px hairline borders instead of elevation/shadow.

This means the words "polish" and "make it easier to look at" have to be
answered *inside* that constraint, not by importing generic modern-SaaS
patterns (soft shadows, spring-bounce animations, pastel accent colors,
rounded cards). Every section below says explicitly which techniques are
in-bounds and which aren't, so "polish" doesn't quietly become "make it
look like Mint" one recommendation at a time.

---

## 1. Animation

### What exists today
There's already a real animation system, just a small, underused one:
`widgets.ANIMATE` (a global on/off switch, forced off in headless test
capture) gates `_reveal_anim()` (`widgets.py:82`) — a 340ms `OutCubic`
`QVariantAnimation` that repaints a widget as a `_reveal` value climbs
0→1, which chart `paintEvent`s can read to draw themselves "growing in."
**Only two chart classes use it** — `GroupedBarChart` (Budget vs actual)
and `StackedBarChart` (Spending composition) — out of roughly ten custom
chart widgets. Everything else (the donut, the fan chart, the area chart,
line charts, the timeline) draws instantly, no entry animation at all.
Separately, **page switches have zero transition** — `MainWindow.go()`
(`main.py:2998`) calls `QStackedWidget.setCurrentWidget()`, an instant cut,
every time the sidebar is clicked.

### What's in-bounds
Given §0, the right animation vocabulary here is **information reveal**,
not decoration — motion that helps the eye track *what changed*, never
motion for its own sake (no bounce, no overshoot, no spring easing — the
existing `OutCubic` choice is exactly right: fast-then-settle, no
overshoot). Concretely:

- **Extend `_reveal_anim` to the rest of the charts** (`FanChart`,
  `AreaChart`, `DonutChart`, `LineChart`, `SubscriptionTimeline`) using the
  exact same pattern already proven in `GroupedBarChart`/`StackedBarChart`
  — each `paintEvent` scales its drawn extent by `self._reveal`. This is
  the single highest-value, lowest-risk animation addition: it's
  mechanical (copy an existing, working pattern into more classes) and
  makes the whole Analytics page feel like one consistent system instead
  of "two charts animate, eight don't."
- **A short crossfade on page switch** — wrap `QStackedWidget` navigation
  in a ~120–150ms opacity animation (`QGraphicsOpacityEffect` +
  `QPropertyAnimation` on the incoming widget) instead of an instant cut.
  Keep it *short* — this is wayfinding (confirms the click registered and
  something changed), not a transition to admire. Longer than ~150ms will
  read as the app being slow, which directly fights the "precise,
  no-nonsense" brand personality.
- **Value-change animation on the Overview hero P&L number** — when the
  month changes or data updates, animate the displayed number counting
  from its old value to the new one (interpolate the float over ~200ms,
  same `QVariantAnimation` pattern, formatting through `money()` each
  tick). This one is specifically justified by `PRODUCT.md`'s "numbers
  lead" principle — animating the *number itself* changing draws the eye
  to the one thing the page is about, more directly than animating chrome
  around it would.
- **Row insert/remove in ledger lists** — when `LedgerCard.rebuild()` adds
  or removes a `CategoryRow`, a brief height/opacity transition on
  add/remove would prevent the "did that actually delete?" uncertainty a
  hard cut can cause in a dense list. Lower priority than the above three
  — it's the most implementation work (rebuild() currently clears and
  rebuilds the whole list rather than diffing it) for a real but smaller
  payoff.

### What's out of bounds
No bounce/spring/elastic easing (reads as playful, contradicts "precise and
no-nonsense"). No hover-triggered scale/grow effects on cards or buttons
(a very common modern-SaaS pattern, but it's decorative motion with no
information content — exactly what §0 rules out). No animated gradients or
shimmer/skeleton loading states (implies a slower, more "consumer app"
feeling app than this is; the existing plain empty-state text is more
on-brand than a shimmer placeholder would be).

**Verify:** with `widgets.ANIMATE = False` (already forced off for headless
capture), every animation added must degrade to its final state instantly
with no visual artifact — this is already how `_reveal_anim` is written
(`if not ANIMATE: widget._reveal = 1.0; return None`); any new animation
must follow the same pattern, not assume `ANIMATE` is always `True`.

---

## 2. Polish

"Polish" here means finishing details that are inconsistent across an
otherwise-coherent app — the kind of thing that doesn't show up as a
single bug but adds up to a slightly-unfinished feeling.

- **Keyboard-focus visibility is inconsistent.** `draw_focus_ring()`
  (`widgets.py:212`) — a clean, on-brand 1px `T.FOCUS`-colored rectangle,
  no glow/shadow — exists and is used by exactly 3 widgets (confirmed by
  grep). Every other custom-painted interactive element (chart hover
  targets, `Clickable` instances used as buttons elsewhere, category rows)
  either doesn't paint a focus indicator at all or relies on Qt's default
  (which may not render meaningfully on a borderless custom widget). For a
  "precise" tool that's explicitly meant to be driven at a desk regularly,
  keyboard navigability should be reliable everywhere, not in 3 spots.
  Audit every `QWidget` subclass with `setFocusPolicy` enabled and confirm
  it calls `draw_focus_ring` in its `paintEvent`.
- **Empty-state styling was inconsistent until this session's fixes**
  (`docs/hands-on-ux-critique-2.md` #6, `docs/full-review-oct-nov-2026.md`)
  — now standardized on `T.TEXT_DIM, 11` + `setWordWrap(True)` + a
  "No X yet — do Y, then Z happens" wording pattern. Worth a final sweep:
  grep for `T.TEXT_DIM` labels used as placeholder/empty text across
  `main.py` and confirm every one follows the pattern now, since it was
  fixed piecemeal rather than all at once.
- **Tooltip coverage is uneven.** Some icons/affordances have `setToolTip`
  (the `↻` recurrence glyph, the `#` tag button), others — like chart
  legend swatches or the `⋯` ledger overflow button before this session's
  fix — didn't until specifically reviewed. A single pass confirming every
  icon-only (no text label) clickable element has a tooltip would close
  this systematically rather than one-off.
- **Hover-affordance discoverability.** Several actions only appear on
  hover (`+` add-sub-item, the `#` tag button, edit/remove on ledger rows)
  — correct for keeping the dense view uncluttered at rest, but means a
  first-time (or returning-after-a-gap, per `review-methodology.md` §1.B)
  user has no static hint these exist. Consider a very brief (one-time,
  dismissible) hint on first launch, or make hover-revealed actions
  slightly more discoverable via a persistent-but-subtle indicator (e.g. a
  faint `⋯` always visible instead of `opacity:0` until hover) rather than
  fully invisible until moused over.
- **Loading/busy feedback for the one genuinely slow operation.** Bank
  import (`_import_bank`, `main.py`) processes a file synchronously with
  no progress indicator — fine for a handful of transactions, but there's
  no signal to the user that anything is happening if a large file takes a
  moment. A simple "Importing…" status swap (already have `import_status`
  to repurpose) before the parse call would close this without adding any
  new UI surface.

**Verify:** each polish item above is a "sweep the whole app for
consistency" task, not a single-file fix — grep for the pattern in
question (`setToolTip`, `draw_focus_ring`, `T.TEXT_DIM.*11\)` for empty
states) across `main.py`/`widgets.py` and confirm coverage is complete, not
just spot-fixed in the one place that happened to get reviewed.

---

## 3. Thematic changes

Within `theme.py`'s existing flat/dark/functional-color system — not a
different system.

- **The categorical color collision is already fixed this session**
  (`docs/aesthetics-recommendations.md` #1/#2) — `SERIES` no longer shares
  hex values with `GREEN`/`RED`/`AMBER`, and `T.category_color(name)` gives
  every category a stable color across charts instead of a chart-local
  position. Mentioned here for completeness — nothing further needed on
  this specific point, it's done.
- **Typography now uses Segoe UI** (switched this session from Arial
  Nova) — Microsoft's UI-purpose-built sans, tuned for small-size
  legibility, which matters here since this app renders a lot of 10–13px
  text. Worth periodically re-checking contrast at the smallest sizes
  (`T.TEXT_DIM` at 10px, used for hints/dates) against `BG_CARD`/
  `BG_CARD_SOFT` as new UI gets added — the accessibility note in
  `PRODUCT.md` sets a ≥4.5:1 bar for body text, and it's easy for a new
  small-text element to quietly fall under that bar if it's copy-pasted
  from a slightly-different-context existing label without rechecking.
- **Hierarchy via top-border accent, extended.** This session added
  `card(accent=T.ACCENT)` (`main.py`) and applied it to Analytics' 4
  Tier-1 charts. It's a cheap, on-brand hierarchy tool (reuses the pattern
  already established by the Overview ledger cards) that's currently used
  in exactly one place. Consider it for other "this is the most important
  thing on this page" moments — e.g. Goals' "Progress to target" bar,
  Subscriptions' monthly-cost tile — rather than inventing a new hierarchy
  mechanism each time one's needed.
- **A genuinely optional idea, not a recommendation: a light theme.**
  `PRODUCT.md` doesn't mention one, and nothing about the current
  single-user, desk-based usage pattern implies it's needed — raised here
  only because "thematic changes" was explicitly asked about. If ever
  wanted, it should be a second token *set* (a `theme_light.py` mirroring
  `theme.py`'s constant names) with the same flat/sharp/functional-color
  rules re-applied at whatever lightness works, not a lightened version of
  the dark palette's exact hues — but this is speculative, not something
  the current brief calls for. Don't build this unprompted.

**Verify:** any theming change should render correctly in both the normal
app (`python main.py`) and the headless `--shot` capture path — several
tokens (`T.FONT_FAMILY`, `T.SERIES`) are exercised by both, and a change
that only shows correctly in one is incompletely tested (see
`review-methodology.md` §2.F).

---

## 4. Simplification — reduce accidental complexity, not density

This is the section where "make it simpler" and `PRODUCT.md`'s "density is
a feature, not a defect" most need reconciling, so the framing matters:
**simplify what isn't earning its place, not what's merely dense.** A
page with 10 well-differentiated, all-useful charts is dense and fine; a
page with 3 charts that each restate what another one already shows is
*complex without being informative*, and that's what should get cut —
exactly the distinction `docs/analytics-graphics-review.md`'s tiering
method (§2.D in `review-methodology.md`) already applies successfully
(Analytics went from 15 graphics to 10 this session, each cut justified by
"this restates a question another element already answers," never by "this
page just felt busy").

Apply the same lens to build cuts elsewhere. Concretely, ask the one-sentence
test — *what question does this answer, and is it the only place that
question is answered* — of:

- **Any page not yet reviewed this way.** The Analytics review method was
  applied to exactly one page. Subscriptions, Settings, and Goals haven't
  had the same inventory-and-tier treatment — Settings in particular has
  accumulated several cards over this session (accounts, categorisation
  rules, bank sync, sidebar tabs, modules) that have never been reviewed
  together as a set for overlap or ordering.
- **Interaction paths, not just visual elements.** Several fixes this
  session simplified a *workflow* rather than cutting a *widget* — the
  Tab-to-amount flow on new ledger items, single-click search activation,
  the recurring-scope prompt no longer firing on a brand-new item's first
  edit. This is the same "simplify" instinct applied to interaction
  friction instead of screen real estate, and it's worth continuing to
  apply: any flow that takes more clicks/fields than the task actually
  needs is complexity that isn't earning its place, exactly like a
  redundant chart.
- **Progressive disclosure for genuinely advanced features, instead of
  cutting them.** Recurring-rule editing, custom split shares on a shared
  plan, and per-occurrence overrides are real, used complexity that
  `PRODUCT.md` explicitly wants kept ("comfortable showing real
  complexity... rather than smoothing it into a friendlier but vaguer
  summary") — the simplification lever for these isn't removal, it's
  making sure they stay tucked behind an explicit action (a dialog, an
  expand toggle) rather than always-visible, so the common path (add an
  item, give it an amount) stays as few steps as it already is after this
  session's fixes, while the advanced path stays fully available for when
  it's needed.

**Verify:** for any proposed simplification, write the one-sentence "what
question does this answer" test *before* deciding to cut — if the answer
is "it's dense" rather than "another element already answers this," it's
not a simplification candidate per `PRODUCT.md`, it's just density, which
this app is allowed to have.

---

## Priority order

1. **Extend `_reveal_anim` to the remaining charts** (§1) — mechanical,
   low-risk, closes an inconsistency the app already half-solved.
2. **Focus-ring and tooltip coverage sweep** (§2) — cheap correctness-of-
   polish work, no design decisions required, just consistent application
   of patterns that already exist and already work.
3. **Page-switch crossfade + hero-number count animation** (§1) — more
   implementation work than #1, but the two highest-leverage *new* motion
   additions for how the app feels to drive day to day.
4. **Settings' card-by-card review using the Analytics-review method**
   (§4) — same proven method, unapplied surface; do this before adding any
   *new* Settings cards so the review isn't immediately stale.
5. **Row insert/remove animation, hover-affordance discoverability, import
   busy-state** (§1/§2) — real but smaller payoff, do after the above.
6. **Light theme** (§3) — only if and when actually requested; not a
   standing recommendation.

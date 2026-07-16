# Aesthetic & UX critique, and a Notion-based overhaul

**Method:** ⚠️ DEGRADED: single-context (no sub-agent delegation — this harness
restricts spawning agents to explicit user request). The bundled `detect.mjs`
deterministic scanner was also **not run**: it parses HTML/CSS, and this is a
PyQt6 desktop app with no markup surface. Every finding below is hand-derived
from source reading, headless screenshots of all six pages
(`python main.py --shot <path> --page <name>`), and computed WCAG math. Two
findings are confirmed against the code, not inferred from pixels.

**Grounding:** *UI Design Principles* (Michael Filipiuk) and *UI/UX Design Guide*
(Joel Parker Henderson), cited inline by page. Target aesthetic: Notion.

**What this document assumes about the user.** Read off the app itself, not off
any brief: a single person, managing their own money, importing ANZ/ANZ Plus
statements, splitting subscriptions with named housemates, tracking savings
goals. Someone technical enough to have written this, at a desk, returning to it
regularly. Every persona judgement below derives from that and nothing else.

---

## 1. Design health score (Nielsen's heuristics, Henderson p80)

| # | Heuristic | Score | Key issue |
|---|-----------|-------|-----------|
| 1 | Visibility of system status | 3 | Solid. Import shows a busy-state, the hero number counts to its new value, pages crossfade. Live bank sync still self-describes as "a scaffold — untested." |
| 2 | Match system / real world | 2 | "P&L", "Pr", "Rate", "Fixed", "ISO weeks (Mon–Sun, cross-month)". Accounting and dev jargon in a personal tool. Henderson p110 lists unclear labels as a papercut; p122 wants microcopy free of jargon. |
| 3 | User control and freedom | 2 | No undo anywhere. Delete is a one-click `✕` on every ledger row, no confirm, no recovery. Henderson p80 #3 wants a clearly marked emergency exit. |
| 4 | Consistency and standards | 2 | Three button vocabularies: the `_button()` factory, raw `QPushButton` with inline QSS, and `Clickable` labels acting as buttons. Same concept, three looks. Henderson p110 names inconsistent elements explicitly. |
| 5 | Error prevention | 2 | Row delete unconfirmed (see #3). Rule-category free-text can silently never match a budget — mitigated by the completer, not prevented. |
| 6 | Recognition rather than recall | 2 | Icon-only 72px sidebar at 9px, one label rendering as **"Quick sta…"**. Six glyphs (`⋯ ↻ # ✎ ✕ ▸`) carry real function. Henderson p80 #6 wants options visible, not memorised. |
| 7 | Flexibility and efficiency | 2 | No keyboard shortcuts at all. Henderson p115 is entirely unimplemented — and #7 is specifically about accelerators for expert users, which is the only user this app has. |
| 8 | Aesthetic and minimalist design | 2 | Every surface is a bordered box at the same elevation. Nothing recedes; the eye has no entry point. Filipiuk p35. |
| 9 | Error recovery | 3 | Import errors are plain-language and specific: "Could not read file: …", "No transactions found — is this an ANZ CSV/OFX export?" Genuinely good, and rare. |
| 10 | Help and documentation | 2 | Tooltips cover every icon now, but there's no help surface, no first-run guidance, no shortcut reference. |
| **Total** | | **22/40** | **Acceptable — significant improvements needed** |

22/40 is not a disaster. This is a capable, information-dense tool with real
engineering under it: 118 passing tests, a genuine plan-vs-reality reconciliation
model, deterministic hash-stable category colors that survive restarts. It is
held back by **presentation**, not capability — precisely the case where a visual
overhaul pays for itself.

---

## 2. Anti-patterns verdict

**Does it look AI-generated?** No, and that deserves saying up front. Not one of
the usual tells is present: no gradient text, no glassmorphism, no cream/sand
body background, no tracked-uppercase eyebrow above every section, no 01/02/03
numbering, no identical card grid. The categorical palette is hand-tuned. The
muted sage/terracotta pairing is a decision, not a default.

**What it looks like instead is *unfinished-native*** — the failure mode of a
competent engineer designing without a system. Four tells:

**Border-on-everything.** Every card, tile, stat box, and input carries a 1px
border. Filipiuk p34 (common region) says a closed region groups its contents —
but when *every* region is closed, closure stops carrying information. Filipiuk
p35 (figure-ground) is the sharper version: users sort things into foreground and
background instantly, and foreground reads as important and interactive. Here
nothing is background, so nothing is foreground.

**The 1680px full-bleed row.** "Month by month" has five columns totalling ~390px
stretched across a 1500px card. Filipiuk p33: proximity *is* grouping. Detailed in
§4.

**No spacing scale.** `setSpacing` values across the app: 0, 1, 4, 6, 8, 10, 14,
18, 20. Margins: `(18,14,18,14)`, `(20,16,20,18)`, `(10,12,10,10)`. Filipiuk
p50–52 is explicit — pick a base value (8pt for desktop), build multiples, space
everything from that scale. There's no scale here, just numbers that felt right
at the time. This is why the app reads as slightly-off rather than wrong.

**A seven-step type scale in a ~1.1 ratio.** 9, 10, 11, 12, 13, 14, 15px, plus
the hero. 12px versus 13px is below the just-noticeable-difference threshold, so
it reads as inconsistency rather than hierarchy. Filipiuk's typography chapter
(p56+) treats hierarchy as the point of a scale; a scale this tight produces none.

**Deterministic scan:** not applicable (no HTML/CSS surface). Stated rather than
silently skipped.

---

## 3. Confirmed defects

These are bugs. I read them in the source, not off a screenshot.

### [P1] "Worst month" renders a **positive** number in red

`main.py`, the Analytics tile row:

```python
self.tiles2[1].set_value(
    f"{dm.MONTH_ABBR[worst_ym[1]]} {worst_ym[0]}\n{money(min(pnls), cur)}",
    T.RED)
```

`T.RED` is hardcoded regardless of sign. On the live data the tile reads
**"Worst month / Jul 2025 / +$3,469"** — in red. A month where the user cleared
three and a half thousand dollars is painted the same color as an overdue bill.

The color encodes **rank**, not **state**. Every other red in this app means
"money leaving" or "past due". Filipiuk p91 is direct about what red does to a
reader: it's the most visible color, it's used for warnings, *"it's generally
considered to be a negative color."* Painting a profit red spends that signal on
nothing. And Henderson p118's first guideline — don't convey critical information
through color alone — cuts both ways: if color is going to carry meaning, it has
to carry a *true* one.

**Fix:** color by sign, not rank — `T.RED if min(pnls) < 0 else T.TEXT`. The word
"Worst" already communicates the ranking. Color shouldn't double-encode it, and
certainly shouldn't contradict the number's own sign.

### [P2] Zero growth renders as a green ↑

```python
arrow = "↑" if growth >= 0 else "↓"
gcol  = T.GREEN if growth >= 0 else T.RED
```

`growth == 0.0` takes the `>= 0` branch. The live tile reads **"Income growth /
↑0.0%"** in green. Flat is not up.

This is Henderson p110's papercut bug in pure form — individually trivial,
collectively corrosive. The whole value of this app is that its numbers are
trustworthy; an arrow that lies about direction taxes every other number on the
page.

**Fix:** three-way — `↑` / `↓` / `—`, with `T.TEXT_DIM` and no arrow at zero. Use
an epsilon, not `== 0`; this is float division.

### [P2] Expense amounts fail WCAG AA

Computed against the live tokens:

| Foreground | Background | Ratio | Verdict |
|---|---|---:|---|
| `TEXT` `#d4d4d4` | `BG_CARD` | 11.25 | PASS |
| `TEXT_MUTED` `#9a9a9a` | `BG_CARD` | 5.92 | PASS |
| `TEXT_DIM` `#8a8a8a` | `BG_CARD` | 4.83 | PASS |
| `TEXT_DIM` `#8a8a8a` | `BG_CARD_SOFT` | **4.50** | borderline |
| **`RED` `#b86060`** | **`BG_CARD`** | **3.87** | **FAIL** |
| `GREEN` `#5da876` | `BG_CARD` | 5.82 | PASS |
| `AMBER` `#c8944a` | `BG_CARD` | 6.18 | PASS |

`RED` renders every expense amount at **13px bold** in `CategoryRow`. WCAG "large
text" starts at 18.66px, or 14px bold — 13px bold doesn't reach it, so the 4.5:1
bar applies and 3.87:1 misses it. Half the numbers in the primary ledger are the
half that's under-contrast, and they're the half about money going out.

Henderson p118: *"Ensure sufficient contrast between foreground and background
colors."* Filipiuk p86 makes the same point from the other end — pure black is
avoided because contrast that's too high hurts; the corollary is that contrast
too low fails outright.

**Fix:** lift `RED` to ≈`#c87070` (≈4.6:1), or use the existing `RED_BRIGHT`
`#d07878` for row amounts and keep `#b86060` for fills and borders where the bar
doesn't apply.

### [P3] The focus ring shares a hex with the hero number

`FOCUS = "#74c490"` and `GREEN_BRIGHT = "#74c490"` are the same value. The
keyboard-focus indicator is painted in the exact color otherwise reserved for the
single most important number on the Overview page. Not a rendering bug — a
semantic collision. Henderson p118 again: a signal that means two things means
neither. Give focus a hue no data value uses.

### [P3] "Progress to target: 578%"

The Goals bar is pinned full at 578% and can never move. A bar that can't move
isn't a bar — it's a rectangle with a number next to it. Henderson p105 on
progress indicators: the job is to let a user *gauge* where they are. This one
can't. Either clamp the visual at 100% and report the surplus separately ("target
met — $2,869 over"), or make the bar's domain the range it actually needs to span.

---

## 4. Priority issues

### [P1] Full-bleed rows destroy proximity

Filipiuk p33 is the most-violated principle in this app, and the violations are
measurable. From the screenshots:

- **History** — `June 2026` at x≈105, its bar at x≈180, and `in +$5,880 out
  −$2,411 +$3,469` at x≈1440–1630. Two halves of one fact, 1,300 pixels apart.
- **Goals → Edit monthly targets** — the label `Target P&L` at x≈111, its spinbox
  at x≈1520. You saccade the full window width to bind a label to its field.
- **Analytics → Month by month** — 390px of columns in a 1500px card, content
  hugging the left edge, 1,100px of nothing to its right.

Filipiuk p33: *"Elements that are close to each other are likely to be perceived
as a group."* The inverse is the problem — elements this far apart are perceived
as *unrelated*, which is exactly wrong for a label and its own value.

This is also the cheapest fix in the document: one constant, applied in
`scrollable()`.

### [P1] The sidebar truncates its own labels

72px rail, 9px captions, and "Quick start" renders as **"Quick sta…"**. Henderson
p123 on iconography assumes icons *support* recognition; p110 lists unclear labels
as a papercut; p80 #6 wants recognition over recall. A sub-10px caption that
doesn't fit its own container fails all three at once.

### [P1] There is no keyboard layer at all

No Cmd+K, no month stepping, no Delete on a focused row, no Esc convention, no `/`
to search. Henderson p115 lists the payoffs — accelerated workflow, productivity,
**accessibility** — and this app has none of them.

Heuristic #7 (Henderson p80) is specifically *"Shortcuts — hidden from novice
users — may speed up the interaction for the expert user."* The only user of this
app is an expert user. It's a personal tool, used regularly, by the person who
built it. The one heuristic most tailored to this exact situation is the one
scoring lowest.

### [P2] Nothing recedes

Filipiuk p35 (figure-ground) and p222 (card styles: *"make sure you're not mixing
the styles inside one website or app — inconsistency isn't good"*). This app mixes
them everywhere: border **and** fill on every surface simultaneously, all at one
elevation.

On Overview, the hero `+$3,469` competes with eight ledger rows, four weekly P&L
lines, a chart, and three goal bars — every one of them boxed, every one weighted
the same. Filipiuk p10 frames the goal as an *invisible* design that redirects
attention to the app's purpose. Here the chrome is a peer of the content.

Henderson p76 gives this a name: **extraneous cognitive load** — mental effort
caused purely by presentation, contributing nothing to the task. It's the one
category of load p77 says to eliminate ruthlessly, because it's pure waste.

### ~~[P2] Delete is one unconfirmed click, and undo does not exist~~ — **RETRACTED, I was wrong**

**This finding was false.** I asserted "no confirm, no undo, no trash" and built
an "inverted safety gradient" argument on it — that `Clear imported` was guarded
while the unrecoverable row delete wasn't. I did not read `LedgerCard._delete`
before writing it. It does this:

```python
reply = QMessageBox.question(
    self, "Delete", f"Delete \"{node['name']}\"?",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    QMessageBox.StandardButton.No)
if reply != QMessageBox.StandardButton.Yes:
    return
```

Simple items get that confirm, defaulting to **No**. Recurring items get a
*scope* prompt (this occurrence / all) before anything is deleted. So delete is
confirmed, the gradient is not inverted — both actions confirm — and the premise
of the fix was invented.

What survives: **undo genuinely does not exist**. But that's a much weaker
finding than the one I wrote, and it does not justify the proposed change.
Replacing a working confirm with immediate-delete-plus-toast would need reliable
restore at the store layer (`delete_occurrence` has no inverse; it would need a
snapshot/restore API). That is a real feature, not a polish item, and it is not
worth doing to fix a bug that isn't there.

**Action taken:** none. I wrote an `UndoToast` widget for this and then deleted
it rather than ship 58 lines of unused code justified by a false claim.
Henderson p176 (Chesterton's fence) is the lesson, aimed squarely at me: I
proposed tearing out the confirm without first checking whether it existed.

### [P3] Three button vocabularies

The `_button()` factory, raw `QPushButton` + inline QSS (the Danger-zone reset),
and `Clickable` QLabels behaving as buttons (`+ Add item`, `+ sub-item`, `⋯`).
Three shapes for one concept. Henderson p110 lists inconsistent elements as a
papercut; p80 #4 is the heuristic — users shouldn't have to wonder whether
different-looking things do the same kind of thing.

---

## 5. Persona red flags

**Alex (power user)** — not a hypothetical here; this is the actual and only user:
- Zero keyboard shortcuts. Changing month means locating a 20px chevron.
- No bulk actions: 42 uncategorised transactions, handled one at a time.
- No command palette, in a six-page app that already has a working search index.

**Sam (accessibility-dependent)**:
- `RED` expense amounts at 3.87:1 (§3).
- Sign is carried by color **and** a `+`/`−` prefix — this one passes, and it's
  exactly what Henderson p118 asks for. Credit where due.
- Custom-painted charts (`FanChart`, `DonutChart`, `SubscriptionTimeline`,
  `AreaChart`, `LineChart`) expose no accessible name or value. A screen reader
  gets nothing at all from Analytics.
- Focus rings exist on three custom classes plus the recent QSS fallback; the
  chart hover targets remain unreachable.

**Jordan (first-timer)** — reframe this one. A single-user personal tool has no
first-timers. But it has **you in six months**, and that user is functionally
identical: no working memory of what `Pr` meant, or which glyph opens tags.
Henderson p80 #6 (recognition over recall) is the same heuristic either way.
That reframing makes "Quick sta…" and the six unlabelled glyphs worth fixing on
selfish grounds, not accessibility-theatre grounds.

---

## 6. The overhaul: Notion, concretely

### 6.1 Tokens (`theme.py`)

Notion is light-first. Dark vs light shouldn't be a reflex either way, so here's
the scene, stated plainly: *one person at a desk, evening, under a lamp,
reviewing money for ten to twenty minutes at a stretch, in a considered mood.*
That's Notion's own context almost exactly, and Notion ships light by default.

**Recommendation: light becomes the default; the current dark palette is kept as
an alternate,** moved to `theme_dark.py` with its constant names intact. The dark
tokens are good work and shouldn't be discarded to make a point. See §7 item 8 —
this is the one recommendation here I'd actively defend leaving undone.

```python
# Light (default) — Notion's real neutral ramp, not a lightened dark theme
BG_APP        = "#ffffff"
BG_SIDEBAR    = "#f7f7f5"   # Notion's sidebar grey
BG_CARD       = "#ffffff"   # blocks have NO fill
BG_HOVER      = "#f1f1ef"   # the only background most blocks ever get
BG_INPUT      = "#f7f7f5"
BG_SELECTED   = "#e8f2fc"

TEXT          = "#37352f"   # Notion's ink: warm near-black. Filipiuk p86 — never #000
TEXT_MUTED    = "#787774"
TEXT_DIM      = "#9b9a97"

BORDER        = "#e9e9e7"   # hairline, used SPARINGLY
BORDER_SOFT   = "#f1f1ef"

GREEN         = "#448361"   # verify ≥4.5:1 on white before shipping
RED           = "#c4554d"   # ditto — do not repeat §3's 3.87:1
AMBER         = "#cb912f"
FOCUS         = "#2383e2"   # Notion blue — and NOT any data color (fixes §3)

RADIUS        = 3           # was 0
SPACE         = [4, 8, 12, 16, 24, 32, 48]   # Filipiuk p52 soft grid, base 8
CONTENT_MAX_W = 1100        # was: unbounded
FONT_FAMILY   = "Segoe UI"  # keep — already the right call
```

`SPACE` is the important one. Filipiuk p51 recommends the **soft** grid over the
hard grid — you don't force every element to an 8pt dimension, you only *space*
from the scale. That's a mechanical change with a large payoff and low risk.

Type scale collapses from seven steps to four: `11px` micro-label · `14px`
body/data · `16px` block heading · `30px` hero. Four steps at a ~1.2 ratio produce
hierarchy you can actually see, which seven steps at 1.1 do not.

### 6.2 Layout

**Sidebar** — 240px, real text labels, collapsible to a 48px icon rail via `[`
(Notion's own shortcut). `Overview / Analytics / Subscriptions / Goals / History`,
a divider, then `Settings`. Full words at 14px. This alone kills the "Quick sta…"
truncation and the §5 recall problem.

**Content column** — `max-width: 1100px`, centered, 96px side padding at ≥1400px.
This is *the* fix for §4's proximity failures: `Target P&L` and its spinbox land
~700px apart at worst instead of 1,400px, and a History row's month and P&L become
readable as a single unit.

Yes, this "wastes" ~580px on a 1680px window. Filipiuk p229 anticipates the
objection precisely — he describes clients repeatedly asking him to *"fill that
empty space"* because it *"looks plain"*, and his answer is that properly used
negative space makes the user focus on what actually matters. p38: margins that
are too small make a design worse. p227: fewer elements on screen means more focus
on the ones there.

**Blocks replace cards.** Strip `border` and `background` from `card()`. A block
becomes: a 16px-semibold heading, its content, a 32px bottom margin. That's the
entire treatment. Background appears on hover only.

This is the direct application of Filipiuk p35 — with no fills anywhere, the
background is finally background, and content is finally foreground. It's also
p222's rule about not mixing card styles, resolved by having one style: none.

### 6.3 Components

| Today | Notion pattern |
|---|---|
| `LedgerCard` rows with an always-live `✕` | Database rows. Left gutter `⋮⋮` + `+` on **row hover**; right-side actions behind a `⋯` menu. Delete moves into that menu, plus an undo toast (§4). |
| Month nav chevrons in the header | Breadcrumb `Budget / July 2026`, with `⌘←` / `⌘→` to step months. |
| `Month / Week` segmented control | Notion's **view switcher** — `Month · Week · Table` as text tabs under the title. |
| `TransactionReviewDialog` (modal) | **Peek panel** from the right. The ledger stays visible behind it — which is the whole point, since you categorise *against* it. Henderson p361 (context switch): co-locate the information a decision needs. |
| `Edit monthly targets` (label ← 1,400px → spinbox) | **Property rows**: 180px label column, value immediately adjacent. Notion's page-properties pattern, and the direct antidote to §4. |
| Settings' nine stacked cards | **Toggle blocks**. Henderson p100 (accordion UI) — space efficiency, progressive disclosure, visual clarity. `Bank & import` open; `Modules`, `Live sync (beta)`, `Danger zone` collapsed. |
| `⋯ ↻ # ✎ ✕` glyphs | Keep them — but as hover-gutter actions with tooltips, not always-on chrome. |
| — | **`Cmd+K` command palette.** New. Jump to page, jump to month, add item, run import. Highest-leverage single addition, per §4 and Henderson p115. |

On the toggle blocks and the peek panel — both are Henderson p77's *"Leverage
Progressive Disclosure: present information and options gradually, only when
needed."* And both are Tesler's Law (p174) applied honestly: the complexity in
recurrence rules and split shares is real and can't be deleted, so it gets moved
behind an explicit action rather than pretending it isn't there.

### 6.4 Motion

The existing motion is already close to right and should mostly survive: 130ms
page crossfade, 180ms row fade-in, 280ms hero count-up, 340ms chart reveal, all
`OutCubic`, all gated behind `widgets.ANIMATE` so headless capture is
deterministic. That restraint matches Notion's. Two changes:

- Chart reveal 340ms → 200ms; it's the one duration meaningfully above the band.
- Add the undo toast (§4): 150ms slide in, 5s dwell.

Do **not** add hover-scale, spring, bounce, or stagger. The instinct already in
this codebase is correct — Henderson p110 lists *lack* of visual feedback as the
papercut, not absence of decoration.

---

## 7. Sequence

Ordered by value ÷ risk, not by section order.

1. **§3's defects** — half a day. The red positive number, the ↑0.0%, and the
   3.87:1 red are wrong *today*, independent of any overhaul. Ship these first
   whatever you decide about the rest.
2. **`CONTENT_MAX_W = 1100`** — one constant in `scrollable()`. Fixes the worst
   proximity failures on four pages. Best ratio in the document by a distance.
3. **240px text sidebar** — kills the truncation and the recall problem.
4. **Tokens + `RADIUS = 3` + the `SPACE` scale + the 4-step type scale** —
   mechanical, wide blast radius, needs a screenshot pass across all six pages.
5. **De-border `card()` → blocks** — the change that actually *reads* as Notion.
   Do it after 4; it depends on the spacing scale existing.
6. **`Cmd+K`, month keys, Delete-with-undo** — the keyboard layer. Biggest real
   win for the only person who uses this.
7. **Peek panel replacing the review modal** — largest lift; last.
8. **Light theme as default** — genuinely optional. Notion-*structure* in
   Notion-*dark* is a coherent product. The existing dark palette is good work.
   You don't have to take the light mode to take the layout.

Items 1–3 total roughly a day and deliver most of the perceptible gain. Items 4–6
are the overhaul proper. Item 7 is a project.

---

## 7a. Implementation status — applied 2026-07-16

Items 1–6 applied; item 7 (peek panel) deferred by decision; item 8 (light theme)
declined — dark palette kept, Notion *structure* taken without Notion's light
mode. 118 tests pass; all six pages verified by headless screenshot.

| # | Item | Status |
|---|------|--------|
| 1 | §3 defects | ✅ all five |
| 2 | `CONTENT_MAX_W = 1100` | ✅ + header aligned to the same column |
| 3 | 240px text sidebar | ✅ collapsible, full labels |
| 4 | Tokens / radius / spacing / type | ✅ |
| 5 | De-border → blocks | ✅ |
| 6 | Keyboard layer | ⚠️ partial — palette + shortcuts shipped, undo **not** (see retraction in §4) |
| 7 | Peek panel | ⏸ deferred |
| 8 | Light theme | ❌ declined |

**Corrections to this document, found while applying it:**

- **§4's delete finding was false** and is retracted above. Delete already
  confirms.
- **The sidebar shortcut is `Ctrl+\`, not `[`.** §6.3 said Notion binds `[`; it
  doesn't — Notion uses `Cmd/Ctrl+\`. A bare `[` is also actively unsafe here:
  Qt consults the shortcut map *before* the focused widget, so an
  ApplicationShortcut on a printable key can be swallowed while typing an item
  name. (I could not reproduce this headlessly — synthetic events bypass
  `QShortcutMap` — so this is reasoning, not a measured result. `Ctrl+\` avoids
  the question entirely and is the accurate binding.)
- **The `accent` card variant was removed, not kept.** §6 assumed a 2px
  `T.ACCENT` top rule would survive as the one remaining border. Once everything
  else went chrome-free it failed twice: a lone 1100px rule read as a *divider*
  rather than emphasis, and `T.ACCENT` is green — the income colour — sitting
  above "Spending composition", an expense chart. That's the same rank-vs-state
  error as the red "Worst month" in §3. Hierarchy is carried by heading weight
  instead. `LedgerCard` keeps its green/red top rule because there the colour is
  *functional* (income vs expense), which is the opposite case.
- **The type scale is five steps, not four.** `FS_METRIC` (20px) was added: a
  stat-tile value is neither body text nor the page's answer, and collapsing it
  into either was a scale that's tidy on paper and wrong on screen.
- **De-bordering broke the inputs.** `BG_INPUT` was `#0e0e0e` — a recessed well
  against the old `#1e1e1e` card fill. With blocks transparent, fields sit on
  `BG_APP` (`#111111`) instead, where `#0e0e0e` is **1.02:1** — invisible. Fixed
  by making fields *lighter* than the page (`#1e1e1e`), as Notion does in
  reverse, plus a stronger `BORDER_LIGHT`. No flat grey reaches 1.4.11's 3:1 on
  `#111111` (even `#5a5a5a` is 2.74), so the boundary is carried by fill **and**
  border together.

**Final palette audit** — every ink now clears 4.5:1 on every surface:

| Ink | BG_APP | BG_CARD | BG_CARD_SOFT | BG_SIDEBAR |
|---|---:|---:|---:|---:|
| TEXT | 12.74 | 11.25 | 10.47 | 11.98 |
| TEXT_MUTED | 6.71 | 5.92 | 5.52 | 6.31 |
| TEXT_DIM | 5.91 | 5.22 | 4.86 | 5.56 |
| GREEN | 6.59 | 5.82 | 5.42 | 6.20 |
| **RED** | 5.77 | **5.10** *(was 3.87)* | 4.75 | 5.43 |
| AMBER | 7.01 | 6.18 | 5.76 | 6.59 |
| FOCUS | 5.29 | 4.67 | 4.35 | 4.98 |

`FOCUS` at 4.35 on `BG_CARD_SOFT` is under the *body-text* bar but is only ever
painted as a ring or `border-color` (verified: `QPen` in `draw_focus_ring`, plus
three QSS `border` rules — never a text colour), so the applicable bar is
1.4.11's 3:1, which it clears.

**Shortcuts shipped:** `Ctrl+K` palette (29 actions, subsequence match — "jul"
finds *Jump to Jul 2026*), `Ctrl+F` search, `Ctrl+←/→` month, `Ctrl+T` today,
`Ctrl+1‑5` pages, `Ctrl+,` settings, `Ctrl+\` sidebar.

---

## 8. Questions worth answering before item 4

- **Is the density load-bearing, or was it a rationalisation?** The earlier
  Analytics pass cut 15 graphics to 10 and the page improved. That's evidence at
  least some of the density was self-justification rather than information. Worth
  being honest about before committing to a layout built on whitespace.
- **What do you actually do forty times a week?** If the honest answer is "look at
  the hero number and close it," then Overview is five blocks too long, and the
  right move isn't Notion at all — it's deletion. Tesler's Law (Henderson p174)
  cuts here too: complexity you remove outright never has to be relocated.
- **What breaks if the app opens on the number and nothing else?** Worth
  prototyping before spending item 5's effort on making twelve blocks prettier.

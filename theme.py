"""Central design tokens: colour palette, sizing, fonts and the global stylesheet.

Dark theme, Notion-derived structure. Functional colour for income/expenses.

Layout follows Notion's model rather than a bordered-card model: content lives in
a bounded, centred column (CONTENT_MAX_W) so a label and its value stay near each
other (Filipiuk p33 — proximity *is* grouping); surfaces carry no border or fill
by default and earn a background only on hover, so the background can actually
read as background (Filipiuk p35 — figure-ground). Spacing comes from the SPACE
scale, never ad-hoc numbers (Filipiuk p50-52 — soft 8pt grid).
"""

# --------------------------------------------------------------------------- #
#  Colours
# --------------------------------------------------------------------------- #
BG_APP        = "#111111"   # base background (near black)
BG_SIDEBAR    = "#181818"   # left navigation rail
BG_HEADER     = "#181818"   # top bar
BG_CARD       = "#1e1e1e"   # panels / cards
BG_CARD_SOFT  = "#242424"   # nested rows, sub-boxes, tiles
BG_HOVER      = "#2c2c2c"   # row / button hover
BG_INPUT      = "#1e1e1e"   # editable fields — LIGHTER than BG_APP, not darker.
                            # Was #0e0e0e, which read as a recessed well against
                            # the old #1e1e1e card fill. Blocks are transparent
                            # now, so fields sit on BG_APP (#111111) instead and
                            # #0e0e0e against it is 1.02:1 — literally invisible.
                            # Notion does the same thing in reverse (#f7f7f5 on
                            # white): a field is lighter than its page, not darker.
BG_PILL       = "#303030"   # active segmented-button background

BORDER        = "#2c2c2c"   # default hairline border
BORDER_SOFT   = "#202020"   # subtle divider
BORDER_LIGHT  = "#454545"   # raised border / input boundary
                            # No flat grey reaches WCAG 1.4.11's 3:1 against
                            # BG_APP without looking like a light-mode escapee
                            # (#5a5a5a is still only 2.74:1), so a field's
                            # boundary is carried by fill AND border together
                            # (1.13:1 + 1.97:1) rather than either alone.

TEXT          = "#d4d4d4"   # primary text                    (11.25:1 on BG_CARD)
TEXT_MUTED    = "#9a9a9a"   # secondary / labels               (5.92:1 on BG_CARD)
TEXT_DIM      = "#909090"   # tertiary (dates, hints)          (4.86:1 on BG_CARD_SOFT)
                            # was #8a8a8a — 4.50:1 on BG_CARD_SOFT sat exactly on
                            # the AA bar with no margin; nudged up so the tightest
                            # surface pairing still clears it.

GREEN         = "#5da876"   # income / positive (muted sage)    (5.82:1 on BG_CARD)
GREEN_BRIGHT  = "#74c490"   # hero P&L number                   (7.97:1 on BG_CARD)
GREEN_BG      = "#192219"   # "Incoming" stat box fill
GREEN_BORDER  = "#243824"

RED           = "#cc7676"   # expense / negative (muted terracotta)
                            # 5.10:1 on BG_CARD, 4.75:1 on BG_CARD_SOFT. Was
                            # #b86060 at 3.87:1 — used for every expense amount at
                            # 13px bold, which is *not* WCAG "large text" (needs
                            # >=18.66px, or >=14px bold), so the 4.5:1 body bar
                            # applied and it missed. Lifted until it clears on
                            # every surface it actually lands on.
RED_BRIGHT    = "#e08c8c"   # hover / emphasis                  (6.59:1 on BG_CARD)
RED_BG        = "#221818"   # "Outgoing" stat box fill
RED_BORDER    = "#382424"

AMBER         = "#c8944a"   # warnings / due-soon               (6.18:1 on BG_CARD)

# Categorical series for donut / breakdown / composition charts (8 distinct
# steps). None of these may equal GREEN/RED/AMBER below — those are reserved
# functional colours (income/expense/warning) and a category landing on one
# of them would silently borrow that meaning (e.g. an arbitrary expense
# category rendering in the exact red used everywhere else for "over
# budget"). Assign per-category via category_color() below, not by a chart's
# own local sort position, so the same category reads as the same colour on
# every chart that shows it.
SERIES = [
    "#7a92a8",  # slate blue-gray
    "#6b8fc4",  # steel blue
    "#9a7a94",  # dusty mauve
    "#a89268",  # muted gold/tan
    "#7a68a8",  # muted purple
    "#4aacac",  # teal
    "#c47a5a",  # copper
    "#8ab060",  # yellow-green
]


def category_color(name: str) -> str:
    """Stable colour for a category/tag/subscription name — the same name
    always maps to the same SERIES slot, regardless of a chart's own local
    sort order or which other categories happen to be present alongside it.
    Uses a deterministic FNV-1a-style hash (not Python's built-in hash(),
    which is randomised per-process for str) so the mapping is also stable
    across app restarts, and mixes well enough that short, similar-length
    names (e.g. "Water"/"Wifi") don't cluster onto the same slot the way a
    plain character-sum hash would."""
    h = 2166136261
    for c in (name or ""):
        h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
    return SERIES[h % len(SERIES)]

# Priority squares
DOT_OVERDUE   = "#cc5555"   # red  – past due
DOT_SOON      = "#c8944a"   # amber – due soon
DOT_OK        = "#5da876"   # green – settled / fine

ACCENT        = GREEN       # "#5da876"
ON_ACCENT     = "#0d1a10"   # text placed on top of ACCENT fills

FOCUS         = "#2f8ae5"   # keyboard-focus ring — system blue, deliberately a
                            # hue no data value uses. Previously #74c490, i.e. the
                            # *same hex* as GREEN_BRIGHT (the hero P&L colour): a
                            # focus indicator and "the single most important number
                            # on the page" rendered identically, so neither signal
                            # meant anything on its own. Checked against SERIES
                            # below: nearest categorical colour is 68.7 in RGB
                            # distance, so it can't be read as a category either.
                            # 4.67:1 on BG_CARD — clears AA as text, and clears the
                            # 3:1 non-text bar for the ring itself.

# --------------------------------------------------------------------------- #
#  Spacing scale  (Filipiuk p50-52: soft 8pt grid)
# --------------------------------------------------------------------------- #
# A *soft* grid, not a hard one: element dimensions are free, but every gap and
# margin comes from this scale. Before this existed the app used setSpacing values
# of 0/1/4/6/8/10/14/18/20 and margins of (18,14,18,14), (20,16,20,18),
# (10,12,10,10) — numbers that felt right individually and read as slightly-off
# collectively. Prefer the names over raw ints at call sites.
SPACE = [4, 8, 12, 16, 24, 32, 48]
SP_XS, SP_S, SP_M, SP_L, SP_XL, SP_2XL, SP_3XL = SPACE

# --------------------------------------------------------------------------- #
#  Type scale
# --------------------------------------------------------------------------- #
# Five steps, each a visible jump (ratios 1.27 / 1.14 / 1.25 / 1.5). The previous
# scale ran 9/10/11/12/13/14/15px — seven steps at ~1.1, which is below the
# just-noticeable-difference threshold, so 12px next to 13px read as
# inconsistency rather than hierarchy.
#
# FS_METRIC exists because a numbers-first tool genuinely needs a step between
# body and hero: a stat tile's value is not body text and not the page's answer.
# Collapsing it into either would be a scale that's tidy on paper and wrong on
# screen.
FS_MICRO  = 11              # column captions, hints, timestamps
FS_BODY   = 14              # body text, ledger rows, data
FS_HEAD   = 16              # block headings
FS_METRIC = 20              # stat-tile values
FS_HERO   = 30              # the one number a page exists to answer

# --------------------------------------------------------------------------- #
#  Sizing
# --------------------------------------------------------------------------- #
SIDEBAR_W           = 240   # was 72 — an icon rail whose 9px captions truncated
                            # ("Quick start" rendered as "Quick sta…")
SIDEBAR_W_COLLAPSED = 48    # icon-only, toggled with "["
HEADER_H            = 56
RADIUS              = 3     # was 0
RADIUS_SM           = 3

CONTENT_MAX_W = 1100        # was unbounded. A 1680px window stretched five ~390px
                            # columns across 1500px and put a label at x=111 with
                            # its own spinbox at x=1520. Filipiuk p33: elements far
                            # apart read as *unrelated*, which is exactly wrong for
                            # a field and its label. The ~580px this "wastes" is
                            # answered by Filipiuk p229 — negative space is what
                            # creates focus; "it looks plain" is not a reason to
                            # fill it.

GAP         = SP_M          # gutter between the three main columns
GAP_SECTION = SP_2XL        # visual "paragraph break" between topic clusters
BLOCK_GAP   = SP_2XL        # bottom margin under a block (replaces card borders
                            # as the grouping mechanism)

WIN_W       = 1680
WIN_H       = 980

FONT_FAMILY       = "Segoe UI"         # base UI font — Microsoft's UI-purpose-built
                                        # sans, tuned for small-size legibility; a
                                        # cleaner, more neutral choice than Arial Nova
                                        # for a dense, numbers-heavy dashboard
FONT_FAMILY_LIGHT = "Segoe UI Light"   # large display numbers only (>= ~18px)

# --------------------------------------------------------------------------- #
#  Fluid UI scale
# --------------------------------------------------------------------------- #
# A single global multiplier the app nudges up/down with the window width, so
# text (and the text-sized controls that grow with it) scale *slightly* on a
# larger monitor. Deliberately a narrow band — this is a gentle zoom, not a
# reflow: at the band's extremes a 14px body is 13px / 16px, which every fixed
# container (32px rows, the sidebar) still comfortably holds, so scaling fonts
# never clips a layout. Runtime code sets UI_SCALE via widgets.apply_ui_scale().
UI_SCALE = 1.0
_SCALE_LO_W, _SCALE_HI_W = 1280, 2400   # window widths the band maps between
_SCALE_LO,   _SCALE_HI   = 0.92, 1.16   # …and the scale factors at each end


def scaled(px: float) -> int:
    """A base pixel size scaled by the current UI_SCALE (min 1)."""
    return max(1, round(px * UI_SCALE))


def compute_scale(win_w: int) -> float:
    """Map a window width to a slight scale factor, clamped to the band."""
    if win_w <= _SCALE_LO_W:
        return _SCALE_LO
    if win_w >= _SCALE_HI_W:
        return _SCALE_HI
    t = (win_w - _SCALE_LO_W) / (_SCALE_HI_W - _SCALE_LO_W)
    return _SCALE_LO + t * (_SCALE_HI - _SCALE_LO)

# --------------------------------------------------------------------------- #
#  Global stylesheet
# --------------------------------------------------------------------------- #
def global_qss() -> str:
    return f"""
    * {{
        font-family: "{FONT_FAMILY}", "Segoe UI", "Arial", sans-serif;
        color: {TEXT};
        outline: none;
    }}
    QMainWindow, QWidget#Root {{
        background: {BG_APP};
    }}

    QToolTip {{
        background: {BG_CARD};
        color: {TEXT};
        border: 1px solid {BORDER_LIGHT};
        padding: 4px 7px;
    }}

    /* Thin, flat scrollbars ------------------------------------------------ */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_LIGHT}; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {BORDER_LIGHT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{ height: 0; }}

    /* Dialogs / inputs ----------------------------------------------------- */
    QDialog {{ background: {BG_CARD}; }}
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {{
        background: {BG_INPUT};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS}px;
        padding: 6px 9px;
        selection-background-color: {GREEN};
        selection-color: {ON_ACCENT};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QDoubleSpinBox:focus, QSpinBox:focus {{
        border: 1px solid {FOCUS};
    }}
    /* Global fallback focus indicator: outline:none above (for the custom-
       painted widgets that draw their own ring via draw_focus_ring) also
       suppresses Qt's native focus rectangle on every ordinary QPushButton/
       QCheckBox in the app — without this, a keyboard-focused button or
       checkbox looks identical to an unfocused one. This applies to every
       QPushButton/QCheckBox that doesn't already define its own :focus rule
       (a widget-level stylesheet's own rules still take precedence). */
    QPushButton:focus {{ border-color: {FOCUS}; }}
    /* Checkbox focus is carried by the indicator's border, not by recolouring
       the label: FOCUS is a saturated blue and tinting body text with it would
       read as a link, not as focus. */
    QCheckBox::indicator:focus {{ border: 1px solid {FOCUS}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {BG_CARD};
        border: 1px solid {BORDER_LIGHT};
        selection-background-color: {BG_HOVER};
        padding: 0px;
    }}
    QLabel {{ background: transparent; }}

    /* Spin-box arrow buttons ------------------------------------------- */
    QDoubleSpinBox::up-button, QSpinBox::up-button {{
        subcontrol-origin: border; subcontrol-position: top right;
        width: 18px; border-left: 1px solid {BORDER};
        background: {BG_CARD_SOFT};
    }}
    QDoubleSpinBox::down-button, QSpinBox::down-button {{
        subcontrol-origin: border; subcontrol-position: bottom right;
        width: 18px; border-left: 1px solid {BORDER};
        background: {BG_CARD_SOFT};
    }}
    QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
    QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
        background: {BG_HOVER};
    }}
    QDoubleSpinBox::up-arrow, QSpinBox::up-arrow   {{ width: 7px; height: 7px; }}
    QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{ width: 7px; height: 7px; }}
    """

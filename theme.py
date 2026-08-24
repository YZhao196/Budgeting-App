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
#  Colours — "Quire" palette, replicated from the Claude-Design mock
#  (Budgeting App.dc.html). Neutrals come from the mock's DARK_VARS verbatim;
#  functional green/red/amber are kept from the previous theme (AA-verified)
#  and re-checked against the new, lighter surfaces.
# --------------------------------------------------------------------------- #
BG_APP        = "#1c1c1e"   # canvas — window base
BG_SIDEBAR    = "#242426"   # canvas-soft — the icon rail
BG_HEADER     = "#1c1c1e"   # topbar sits on canvas, separated by a hairline
BG_CARD       = "#28282a"   # surface — cards ("qcard"), dialogs, menus
BG_CARD_SOFT  = "#242426"   # canvas-soft — nested tracks, tiles, seg-mini rails
BG_HOVER      = "#313134"   # row / button hover (one step above surface)
BG_TAG        = "#242426"   # neutral tag-chip fill (metadata, not a state)
BG_INPUT      = "#242426"   # txt-input fill = canvas-soft, on surface cards
BG_PILL       = "#28282a"   # seg-mini active thumb = surface on canvas-soft rail

BORDER        = "#333335"   # hairline — card edges, row dividers, input borders
BORDER_SOFT   = "#2a2a2c"   # quieter divider (between canvas and hairline)
GRID          = "#232325"   # chart gridlines only — faintest ink on a chart
BORDER_LIGHT  = "#48484a"   # hairline-strong — scrollbar thumb, raised edges

TEXT          = "#f0f0f1"   # ink — primary text and figures
TEXT_SECONDARY= "#cfcfd1"   # ink-secondary — month label, row emphasis
TEXT_MUTED    = "#9a9a9d"   # ink-muted — kickers, captions, rail items
TEXT_DIM      = "#939396"   # tertiary (dates, hints) — AA-checked on BG_CARD
TEXT_FAINT    = "#6b6b6e"   # ink-faint — decorative micro-annotations ONLY
                            # (sparkline axis ends); below AA, never for
                            # information that isn't available elsewhere.

PRIMARY       = "#4a72d8"   # deep navy accent — logo fill, progress-bar fills,
                            # hover borders, active-tab underline. Was a paler
                            # sky blue (#5aa2e8); darkened for a richer "dark
                            # blue" read. Only clears WCAG 1.4.11's 3:1
                            # non-text bar (2.03–2.35 for a fully dark navy at
                            # this luminance) — near-black surfaces put a hard
                            # floor on how dark a blue can go and stay visible
                            # at all, so use PRIMARY only on graphical fills/
                            # borders, never as small text. A chrome accent,
                            # deliberately NOT a data state — green/red still
                            # own income/expense meaning.
PRIMARY_TEXT  = "#7d9fe6"   # same navy family, lightened for the two spots
                            # PRIMARY is read as actual small text rather than
                            # a fill or border (the active sidebar-rail caption/
                            # icon, calendar due-date labels) — those need the
                            # 4.5:1 text bar, which the fill-toned PRIMARY above
                            # misses by a wide margin at this small a size.

GREEN         = "#5da876"   # income / positive (muted sage)    (5.82:1 on BG_CARD)
GREEN_BRIGHT  = "#74c490"   # hero P&L number                   (7.97:1 on BG_CARD)
GREEN_BG      = "#192219"   # "Incoming" stat box fill
GREEN_BORDER  = "#243824"

RED           = "#d07c7c"   # expense / negative (muted terracotta)
                            # Lifted again for the lighter Quire surfaces: the
                            # previous #cc7676 sat at exactly 4.50:1 on the new
                            # #28282a card — zero margin. #d07c7c clears 4.5:1
                            # comfortably on every surface expense text lands on.
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


def sign_ramp(n: int, income: bool) -> list:
    """A green-family (income) or red-family (expense) ramp of ``n`` colours for
    a breakdown pie/donut — on-brand, so the pie reads as "this is spending" (red)
    or "this is earning" (green) rather than an off-theme rainbow.

    Ordered light→dark, so a segments-sorted-biggest-first donut puts the
    brightest slice on the largest share. Steps vary in lightness (and drift a
    little in hue) so adjacent slices stay distinguishable within one hue family
    — the trade for staying near green/red is that separation comes from
    lightness, not hue. Muted saturation to match the dark theme, and the band is
    kept off the exact functional GREEN/RED so a slice never *is* the token.

    Unlike category_color this is position-based, not name-based: a category's
    slice colour can shift month to month as its rank changes. That's an accepted
    cost of the green/red look and is confined to the pie + its own legend.
    """
    import colorsys
    base_h = 0.365 if income else 0.020          # green vs red hue
    steps = max(1, n)
    out = []
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0.0
        hue = (base_h + 0.05 * (t - 0.5)) % 1.0  # slight drift for separation
        light = 0.66 - 0.26 * t                  # light (big slice) → dark
        sat = 0.40 - 0.07 * t
        r, g, b = colorsys.hls_to_rgb(hue, light, sat)
        out.append("#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255)))
    return out


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
#  Type scale — mapped from the mock's sizes
# --------------------------------------------------------------------------- #
FS_MICRO  = 11              # kickers (uppercase section labels), hints, captions
FS_BODY   = 13              # body text, ledger rows, data (mock runs 13–13.5px)
FS_HEAD   = 15              # card headings ("Incoming", dialog titles)
FS_METRIC = 22              # stat-tile values
FS_TITLE  = 22              # topbar page title (700, -0.4px tracking)
FS_HERO   = 28              # the one number a page exists to answer

# --------------------------------------------------------------------------- #
#  Sizing — mock geometry
# --------------------------------------------------------------------------- #
SIDEBAR_W           = 76    # icon rail: 56×52 items, 18px icon over 10px caption
SIDEBAR_W_COLLAPSED = 0     # Ctrl+\ hides the rail entirely (mock behaviour)
HEADER_H            = 60
RADIUS              = 12    # radius-md — cards, menus, dialogs
RADIUS_SM           = 8     # radius-sm — inputs, small buttons, rail items, chips
RADIUS_LG           = 16    # radius-lg — modal boxes (palette / search)
RADIUS_PILL         = 999   # radius-full — progress tracks, seg-mini pills
                            # (clamped to height/2 at the draw site)

CONTENT_MAX_W = None        # the mock fills the window on every page; narrow
                            # surfaces (Settings cards) cap their own width at
                            # 520px instead of the page capping content.
SETTINGS_CARD_W = 520       # max-width of a Settings section card (mock value)

GAP          = SP_L         # 16px gutter between cards (mock .content gap)
SCROLL_GUTTER = 16          # gap between scrollable content and the scrollbar
GAP_SECTION = SP_XL         # a larger break between topic clusters (24px)
BLOCK_GAP   = SP_L          # cards carry their own borders again, so page
                            # rhythm tightens back to the mock's 16px grid

WIN_W       = 1680
WIN_H       = 980

FONT_FAMILY       = "Segoe UI"         # base UI font — chosen over Arial Nova for
                                        # a numbers-dense finance UI: genuine
                                        # humanist warmth (not a squeezed grotesque),
                                        # true designed Light/Semibold/Bold weights
                                        # rather than synthesized ones, strong
                                        # tabular figures for aligned money columns,
                                        # and the broadest Unicode/language coverage
                                        # of any common Windows UI font.
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


def input_style(pad: str = "8px 12px") -> str:
    """Shared style for a field styled inline (a field on a dialog/card that
    needs its own BG_INPUT fill). Matches the global QSS / the mock's
    .txt-input: canvas-soft fill, hairline resting border, radius-sm. Covers
    QPlainTextEdit too (the note editor), which the global QSS doesn't reach."""
    sel = "QLineEdit,QPlainTextEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QComboBox"
    return (
        f"{sel}{{background:{BG_INPUT}; color:{TEXT};"
        f" border:1px solid {BORDER}; border-radius:{RADIUS_SM}px; padding:{pad};}}"
        f"{sel.replace(',', ':hover,')}:hover{{border:1px solid {BORDER_LIGHT};}}"
        f"{sel.replace(',', ':focus,')}:focus{{border:1px solid {FOCUS};}}")

# --------------------------------------------------------------------------- #
#  Global stylesheet
# --------------------------------------------------------------------------- #
def global_qss() -> str:
    return f"""
    * {{
        font-family: "{FONT_FAMILY}", "Arial", sans-serif;
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

    /* Thin scrollbars (mock: 6px, rounded, hairline-strong thumb) ---------- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 6px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_LIGHT}; min-height: 30px; border-radius: 3px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {BORDER_LIGHT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{ height: 0; }}

    /* Dialogs / inputs (mock .txt-input: canvas-soft fill, hairline border,
       radius-sm, 8px 12px padding) ---------------------------------------- */
    QDialog {{ background: {BG_CARD}; }}
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {{
        background: {BG_INPUT};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        padding: 8px 12px;
        selection-background-color: {GREEN};
        selection-color: {ON_ACCENT};
    }}
    QLineEdit:hover, QComboBox:hover, QDateEdit:hover,
    QDoubleSpinBox:hover, QSpinBox:hover {{
        border: 1px solid {BORDER_LIGHT};
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

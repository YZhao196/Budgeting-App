"""Central design tokens: colour palette, sizing, fonts and the global stylesheet.

Flat, sharp dark theme. Functional colour for income/expenses; no gradients.
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
BG_INPUT      = "#0e0e0e"   # editable fields
BG_PILL       = "#303030"   # active segmented-button background

BORDER        = "#2c2c2c"   # default hairline border
BORDER_SOFT   = "#202020"   # subtle divider
BORDER_LIGHT  = "#383838"   # raised / focused border

TEXT          = "#d4d4d4"   # primary text
TEXT_MUTED    = "#9a9a9a"   # secondary / labels (>= 4.5:1 on cards)
TEXT_DIM      = "#8a8a8a"   # tertiary (dates, hints)

GREEN         = "#5da876"   # income / positive (muted sage green)
GREEN_BRIGHT  = "#74c490"   # hero P&L number
GREEN_BG      = "#192219"   # "Incoming" stat box fill
GREEN_BORDER  = "#243824"

RED           = "#b86060"   # expense / negative (muted terracotta)
RED_BRIGHT    = "#d07878"
RED_BG        = "#221818"   # "Outgoing" stat box fill
RED_BORDER    = "#382424"

AMBER         = "#c8944a"   # warnings / due-soon

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
FOCUS         = "#74c490"   # keyboard-focus ring

# --------------------------------------------------------------------------- #
#  Sizing  (squared — zero corner radius everywhere)
# --------------------------------------------------------------------------- #
SIDEBAR_W   = 72
HEADER_H    = 56
RADIUS      = 0
RADIUS_SM   = 0
GAP         = 14            # gutter between the three main columns
GAP_SECTION = 28            # extra breathing room between distinct topic
                            # clusters on a long page (e.g. Analytics) — a
                            # visual "paragraph break" uniform spacing can't
                            # provide on its own

WIN_W       = 1680
WIN_H       = 980

FONT_FAMILY       = "Segoe UI"         # base UI font — Microsoft's UI-purpose-built
                                        # sans, tuned for small-size legibility; a
                                        # cleaner, more neutral choice than Arial Nova
                                        # for a dense, numbers-heavy dashboard
FONT_FAMILY_LIGHT = "Segoe UI Light"   # large display numbers only (>= ~18px)

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
        border: 1px solid {BORDER};
        border-radius: 0px;
        padding: 6px 9px;
        selection-background-color: {GREEN};
        selection-color: {ON_ACCENT};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QDoubleSpinBox:focus, QSpinBox:focus {{
        border: 1px solid {FOCUS};
    }}
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

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

TEXT          = "#c8c8c8"   # primary text
TEXT_MUTED    = "#6a6a6a"   # secondary / labels
TEXT_DIM      = "#404040"   # tertiary (dates, hints)

GREEN         = "#5da876"   # income / positive (muted sage green)
GREEN_BRIGHT  = "#74c490"   # hero P&L number
GREEN_BG      = "#192219"   # "Incoming" stat box fill
GREEN_BORDER  = "#243824"

RED           = "#b86060"   # expense / negative (muted terracotta)
RED_BRIGHT    = "#d07878"
RED_BG        = "#221818"   # "Outgoing" stat box fill
RED_BORDER    = "#382424"

AMBER         = "#c8944a"   # warnings / due-soon

# Greyscale series for donut / breakdown charts (8 distinct steps)
SERIES = [
    "#5da876",  # sage green
    "#6b8fc4",  # steel blue
    "#c8944a",  # amber
    "#b86060",  # terracotta
    "#7a68a8",  # muted purple
    "#4aacac",  # teal
    "#c47a5a",  # copper
    "#8ab060",  # yellow-green
]

# Priority squares
DOT_OVERDUE   = "#cc5555"   # red  – past due
DOT_SOON      = "#c8944a"   # amber – due soon
DOT_OK        = "#5da876"   # green – settled / fine

ACCENT        = GREEN       # "#5da876"

# --------------------------------------------------------------------------- #
#  Sizing  (squared — zero corner radius everywhere)
# --------------------------------------------------------------------------- #
SIDEBAR_W   = 72
HEADER_H    = 56
RADIUS      = 0
RADIUS_SM   = 0
GAP         = 14            # gutter between the three main columns

WIN_W       = 1680
WIN_H       = 980

FONT_FAMILY = "Arial Nova Light"   # falls back to a system sans if not installed

# --------------------------------------------------------------------------- #
#  Global stylesheet
# --------------------------------------------------------------------------- #
def global_qss() -> str:
    return f"""
    * {{
        font-family: "{FONT_FAMILY}", "Arial", "Segoe UI", sans-serif;
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
        selection-color: #0d1a10;
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QDoubleSpinBox:focus, QSpinBox:focus {{
        border: 1px solid {BORDER_LIGHT};
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

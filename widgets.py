"""Reusable UI components (the visual building blocks of every page).

Nothing here knows about *which* month is shown – they are handed a month
document plus a few callbacks and render it.  Business maths lives in
``backend``; colours / sizes in ``theme``; vector glyphs in ``icons``.
"""

from __future__ import annotations

import math
import re
import weakref
from datetime import date, timedelta

from PyQt6.QtCore import (QDate, QEasingCurve, QPointF, QPropertyAnimation, QRectF,
                          QSize, Qt, QTimer, QVariantAnimation, pyqtSignal)
from PyQt6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics, QIcon,
                         QLinearGradient, QPainter, QPainterPath, QPen, QPixmap)
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCalendarWidget, QCheckBox, QComboBox, QCompleter,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFrame, QGraphicsOpacityEffect,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget, QWidgetAction,
)

import backend as B
import datamanagement as dm
import icons
import theme as T

# Shared column widths so card headers, rows and sub-rows line up exactly.
W_AMOUNT = 84
W_PAID   = 20          # expense "paid" toggle
W_DUE    = 48
W_PR     = 28
W_ADDED  = 44
ROW_ICON = 17          # a single row-action glyph box (recurrence/tag/note/delete)
W_ACT    = ROW_ICON * 4 + 3 * 3   # the action column holds up to four glyphs
PLUS_W   = 16          # left-side hover "+" that adds a sub-item
CHEV_W   = 14
INDENT   = 16
PAD_L    = 14
PAD_R    = 10
ROW_H    = 34          # a hair more air per ledger row (was 32) — with the fluid
                       # font scale this also keeps text off the row edges

# Entry-reveal animations (disabled in headless --shot mode).
ANIMATE = True


def flash_widget(widget, revert_style="", duration_ms=1500):
    """Briefly tint a widget's background to call it out — used to draw the
    eye to a row that search navigation just jumped to."""
    c = QColor(T.AMBER); c.setAlpha(55)
    widget.setStyleSheet(
        f"background:rgba({c.red()},{c.green()},{c.blue()},{c.alpha()});")
    QTimer.singleShot(duration_ms, lambda w=widget: w.setStyleSheet(revert_style))


def place_near_cursor(dlg):
    """Position a just-created dialog at the cursor, clamped to stay fully on
    the current screen — a plain move(QCursor.pos()) can push a dialog
    launched from a right/bottom-edge button past the screen edge."""
    dlg.adjustSize()
    scr = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
    avail = scr.availableGeometry()
    geo = dlg.frameGeometry()
    geo.moveTopLeft(QCursor.pos())
    geo.moveLeft(max(avail.left(), min(geo.left(), avail.right() - geo.width())))
    geo.moveTop(max(avail.top(), min(geo.top(), avail.bottom() - geo.height())))
    dlg.move(geo.topLeft())


class MoneySpin(QDoubleSpinBox):
    """QDoubleSpinBox that selects its text on focus, so typing immediately
    replaces the value instead of splicing into it (e.g. clicking a "$0.00"
    field and typing "200" would otherwise produce "$0.20")."""

    def focusInEvent(self, e):
        super().focusInEvent(e)
        QTimer.singleShot(0, self.selectAll)


def _reveal_anim(widget):
    """Return a 0→1 QVariantAnimation that repaints ``widget`` each tick, or
    None when animation is disabled (headless).  Widgets read ``_reveal``."""
    if not ANIMATE:
        widget._reveal = 1.0
        return None
    anim = QVariantAnimation(widget)
    anim.setStartValue(0.0); anim.setEndValue(1.0)
    anim.setDuration(340)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _tick(v):
        widget._reveal = float(v)
        widget.update()
    anim.valueChanged.connect(_tick)
    return anim


def _row_fade_in(widget):
    """Brief opacity fade for a freshly-inserted ledger row — confirms the
    "+ Add item"/"+ sub-item" click landed somewhere concrete, not a
    transition meant to be admired: skipped entirely when ANIMATE is off, so
    --shot never catches a row mid-fade."""
    if not ANIMATE:
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setStartValue(0.0); anim.setEndValue(1.0)
    anim.setDuration(180)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._insert_anim = anim             # keep a reference alive
    anim.start()


# Manually-set priority -> dot colour (0 = none)
PRIO_COLORS = {0: None, 1: T.DOT_OVERDUE, 2: T.DOT_SOON, 3: T.DOT_OK}
PRIO_NAMES  = {0: "None", 1: "High", 2: "Medium", 3: "Low"}


# --------------------------------------------------------------------------- #
#  Tiny helpers
# --------------------------------------------------------------------------- #
def money(v: float, currency: str = "$", signed: bool = True,
          cents: bool = False) -> str:
    if cents:
        v = round(float(v), 2)
    else:
        v = round(v)
    if signed:
        sign = "+" if v >= 0 else "-"
    else:
        sign = "-" if v < 0 else ""
    if cents:
        return f"{sign}{currency}{abs(v):,.2f}"
    return f"{sign}{currency}{abs(int(v)):,}"


# Live registry for the fluid UI scale: every label() records its *base* pixel
# size and joins this list (weakly, so it's collected with the widget). When the
# window resizes past a threshold, apply_ui_scale() walks it and re-fits each
# label's font to the new scale — the single mechanism behind "text scales with
# the window", covering all ~240 label() sites without touching one of them.
_scalable_labels: list[weakref.ref] = []


def _scaled_font(base_px: int, bold: bool) -> QFont:
    # Family is chosen from the *base* size (the Light face is for genuinely
    # large display numbers), so a scaled-up small label doesn't switch faces.
    fam = T.FONT_FAMILY_LIGHT if (base_px >= 18 and not bold) else T.FONT_FAMILY
    f = QFont(fam); f.setPixelSize(T.scaled(base_px)); f.setBold(bold)
    return f


def label(text: str, color: str = T.TEXT, px: int = 12, bold: bool = False,
          align=None) -> QLabel:
    lb = QLabel(text)
    lb._base_px = px            # remembered so the fluid scale can re-fit it
    lb._base_bold = bold
    lb.setFont(_scaled_font(px, bold))
    lb.setStyleSheet(f"color:{color}; background:transparent;")
    if align is not None:
        lb.setAlignment(align)
    _scalable_labels.append(weakref.ref(lb))
    return lb


def apply_ui_scale(scale: float, app=None) -> None:
    """Set the global UI scale and re-fit everything that reads it.

    Fonts on label()-made widgets are re-fitted directly; the application
    default font (which the un-styled controls — buttons, inputs, spin-boxes —
    inherit) is scaled too, so they grow in step. Custom-painted widgets read
    T.scaled() at paint time, so they pick the new scale up on their next
    repaint, which the resize itself triggers.
    """
    T.UI_SCALE = scale
    live: list[weakref.ref] = []
    for ref in _scalable_labels:
        lb = ref()
        if lb is None:
            continue
        live.append(ref)
        lb.setFont(_scaled_font(lb._base_px, lb._base_bold))
    _scalable_labels[:] = live
    if app is not None:
        af = app.font()
        af.setPointSizeF(10.0 * scale)     # 10pt is the base set in main()
        app.setFont(af)


def hsep() -> QFrame:
    ln = QFrame(); ln.setFixedHeight(1)
    ln.setStyleSheet(f"background:{T.BORDER_SOFT}; border:none;")
    return ln


def repeat_label(r) -> str | None:
    """Human-readable recurrence, e.g. 'Every 2 weeks' / 'Days 1, 15'."""
    if not r:
        return None
    if r.get("type") == "interval":
        n, unit = int(r.get("every", 1)), r.get("unit", "month")
        return f"Every {unit}" if n == 1 else f"Every {n} {unit}s"
    if r.get("type") == "days":
        days = r.get("days") or []
        if not days:
            return None
        return ("Day " if len(days) == 1 else "Days ") + ", ".join(
            str(d) for d in sorted(days))
    return None


def due_display(due) -> str:
    """Show a stored due date (full ISO or legacy MM-DD) as MM-DD."""
    if not due:
        return "—"
    return due[5:] if len(due) >= 10 else due


def _is_overdue(due, today) -> bool:
    d = B._parse_due(due, today)
    return bool(d and d < today)


class _TagChip(QLabel):
    """A small rounded tag label, optionally clickable (to filter by it)."""
    def __init__(self, text, on_click=None):
        super().__init__(text)
        f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(9)); self.setFont(f)
        # A tag is metadata, not a state: a quiet neutral pill (no border, no
        # accent), so it doesn't borrow green/accent's "income/on-track" meaning
        # (critique §3.2). Notion tags are low-saturation, borderless.
        self.setStyleSheet(
            f"color:{T.TEXT_MUTED}; background:{T.BG_TAG};"
            f"border:none; border-radius:{T.RADIUS_SM}px; padding:1px 7px;")
        self._cb = on_click
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(f"Filter by #{text}")

    def mousePressEvent(self, e):
        if self._cb and e.button() == Qt.MouseButton.LeftButton:
            self._cb()


def tag_chip(text: str, on_click=None) -> QLabel:
    """A small rounded label used to display a tag (clickable if given a callback)."""
    return _TagChip(text, on_click)


def clear_layout(lay):
    """Recursively remove and delete everything in a layout (widgets nested in
    sub-layouts included) so nothing lingers/ghosts after a rebuild."""
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w:
            w.hide()
            w.deleteLater()
        elif it.layout():
            clear_layout(it.layout())


class BoundedScroll(QScrollArea):
    """Wheel events are always consumed — prevents scroll bleeding to a parent scroll area at boundaries."""
    def wheelEvent(self, e):
        super().wheelEvent(e)
        e.accept()


def bounded(inner, max_w=None):
    """Wrap ``inner`` in a host that holds it to a centred column of ``max_w``.

    The single mechanism behind the app's content column. Without a cap, a 1680px
    window stretches five ~390px table columns across 1500px and puts a label at
    x=111 with its own spinbox at x=1520 — which Filipiuk p33 says reads as
    *unrelated*, the opposite of what a field and its label should read as.

    ``max_w=None`` passes ``inner`` straight through, for surfaces that are
    already a narrow column (e.g. Overview's fixed 356px right rail).

    The stretch factor on ``inner`` has to dominate the two spacers or they take
    all the slack and the content renders at its size hint inside the cap. Qt
    honours maximumWidth first, so ``inner`` grows to ``max_w`` and only the
    remainder is split between the spacers.
    """
    if not max_w:
        return inner
    host = QWidget()
    host.setStyleSheet("background:transparent;")
    hl = QHBoxLayout(host)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(0)
    inner.setMaximumWidth(max_w)
    inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    hl.addStretch(1)
    hl.addWidget(inner, 1000)
    hl.addStretch(1)
    return host


def draw_focus_ring(widget, painter=None):
    """Paint a 1px keyboard-focus ring inside a widget's bounds (layout-neutral)."""
    if not widget.hasFocus():
        return
    p = painter or QPainter(widget)
    p.setPen(QPen(QColor(T.FOCUS), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(widget.rect().adjusted(0, 0, -1, -1))


class Clickable(QLabel):
    """A QLabel that behaves like a flat text button (colour shifts on hover).
    Focusable: Tab reaches it, Enter/Space activates it."""
    clicked = pyqtSignal()

    def __init__(self, text, color=T.TEXT_MUTED, px=12, hover=None, bold=False,
                 editable=False):
        super().__init__(text)
        self._c = color
        self._h = hover or T.TEXT
        self._hover = False
        # editable=True marks click-to-edit *text* (a ledger name/amount) rather
        # than a link/button: it gets a text cursor and a quiet dotted underline
        # on hover, so a cold user can see the value is editable without prior
        # knowledge (critique §7; Filipiuk p281 — a clickable thing must look it).
        self._editable = editable
        # Join the fluid-scale registry too (it's a QLabel, so apply_ui_scale
        # re-fits it exactly like a label()): otherwise the many Clickables used
        # as buttons/links ("+ Add item", nav actions) wouldn't scale live.
        self._base_px = px
        self._base_bold = bold
        self.setFont(_scaled_font(px, bold))
        self.setStyleSheet(f"color:{color}; background:transparent;")
        self.setCursor(Qt.CursorShape.IBeamCursor if editable
                       else Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        _scalable_labels.append(weakref.ref(self))

    def set_base_color(self, color):
        self._c = color
        self.setStyleSheet(f"color:{color}; background:transparent;")

    def enterEvent(self, e):
        self._hover = True
        self.setStyleSheet(f"color:{self._h}; background:transparent;")
        if self._editable:
            self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.setStyleSheet(f"color:{self._c}; background:transparent;")
        if self._editable:
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def focusInEvent(self, e):  super().focusInEvent(e);  self.update()
    def focusOutEvent(self, e): super().focusOutEvent(e); self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._editable and (self._hover or self.hasFocus()):
            fm = self.fontMetrics()
            tw = min(fm.horizontalAdvance(self.text()), self.width())
            al = self.alignment()
            if al & Qt.AlignmentFlag.AlignRight:
                x0, x1 = self.width() - tw, self.width()
            elif al & Qt.AlignmentFlag.AlignHCenter:
                x0 = (self.width() - tw) / 2; x1 = x0 + tw
            else:
                x0, x1 = 0, tw
            y = self.height() - 2
            pen = QPen(QColor(self._h), 1, Qt.PenStyle.DotLine)
            p = QPainter(self)
            p.setPen(pen)
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
            p.end()
        draw_focus_ring(self)


# --------------------------------------------------------------------------- #
#  Sidebar navigation
# --------------------------------------------------------------------------- #
class NavButton(QWidget):
    """A sidebar row: icon + full-width text label, Notion-style.

    Was a 72px-wide stacked icon-over-caption tile whose 9px caption truncated
    ("Quick start" rendered as "Quick sta…"). Now a horizontal row — icon left,
    label at FS_BODY beside it — which is what the width is for. In collapsed
    mode the label is dropped and the tooltip carries the name instead.
    """
    clicked = pyqtSignal(str)

    H = 32          # Notion's sidebar row height
    _ICON = 18

    def __init__(self, key, icon, text):
        super().__init__()
        self.key, self.icon, self.text = key, icon, text
        self._active = False
        self._hover = False
        self._collapsed = False
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip(text)

    def setActive(self, a):
        self._active = a
        self.update()

    def setCollapsed(self, c):
        self._collapsed = c
        self.update()

    def enterEvent(self, e): self._hover = True; self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.key)
        else:
            super().keyPressEvent(e)

    def focusInEvent(self, e):  super().focusInEvent(e);  self.update()
    def focusOutEvent(self, e): super().focusOutEvent(e); self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Selected/hover is a filled row, not a left tick-mark: with a real text
        # label the whole row is the target, so the whole row should light up.
        if self._active or self._hover:
            p.setBrush(QColor(T.BG_PILL if self._active else T.BG_HOVER))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(T.SP_XS, 0, self.width() - 2 * T.SP_XS,
                                     self.height()),
                              T.RADIUS, T.RADIUS)

        col = T.TEXT if (self._active or self._hover) else T.TEXT_MUTED
        if self._collapsed:
            x = (self.width() - self._ICON) / 2
        else:
            x = T.SP_M
        icons.draw(p, self.icon,
                   QRectF(x, (self.height() - self._ICON) / 2,
                          self._ICON, self._ICON), col, 1.7)

        if not self._collapsed:
            f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(T.FS_BODY))
            f.setBold(self._active)
            p.setFont(f)
            p.setPen(QColor(col))
            tx = T.SP_M + self._ICON + T.SP_S
            p.drawText(QRectF(tx, 0, self.width() - tx - T.SP_S, self.height()),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       self.text)
        draw_focus_ring(self, p)


class Sidebar(QWidget):
    navigated = pyqtSignal(str)

    # Full words. "Subs" was an abbreviation forced by a 72px rail that no longer
    # exists, and "Quick start" used to render as "Quick sta…".
    ITEMS = [("overview",      "overview",  "Overview"),
             ("analytics",     "analytics", "Analytics"),
             ("subscriptions", "subs",      "Subscriptions"),
             ("goals",         "goals",     "Goals"),
             ("history",       "history",   "History")]

    def __init__(self):
        super().__init__()
        self._collapsed = False
        self.setFixedWidth(T.SIDEBAR_W)
        self.setStyleSheet(f"background:{T.BG_SIDEBAR};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SP_S, 0, T.SP_S, T.SP_M)
        lay.setSpacing(1)
        self._lay = lay

        self.logo = QLabel("$")
        lf = QFont(T.FONT_FAMILY); lf.setPixelSize(T.scaled(22)); lf.setBold(True)
        self.logo.setFont(lf)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setFixedHeight(T.HEADER_H)
        self.logo.setStyleSheet(f"color:{T.ACCENT}; background:transparent;")
        lay.addWidget(self.logo)
        lay.addSpacing(T.SP_XS)

        self.buttons = {}
        for key, ic, text in self.ITEMS:
            b = NavButton(key, ic, text)
            b.clicked.connect(self.navigated.emit)
            self.buttons[key] = b
            lay.addWidget(b)

        lay.addStretch(1)
        # Settings is a different kind of destination from the five content
        # pages, so it sits below a divider rather than in the same run.
        self._divider = hsep()
        lay.addWidget(self._divider)
        lay.addSpacing(T.SP_XS)
        s = NavButton("settings", "settings", "Settings")
        s.clicked.connect(self.navigated.emit)
        self.buttons["settings"] = s
        lay.addWidget(s)

        self.setActive("overview")

    def toggle_collapsed(self):
        """Collapse to an icon-only rail (bound to Ctrl+\\, as in Notion)."""
        self._collapsed = not self._collapsed
        self.setFixedWidth(T.SIDEBAR_W_COLLAPSED if self._collapsed else T.SIDEBAR_W)
        self.logo.setVisible(not self._collapsed)
        self._divider.setVisible(not self._collapsed)
        for b in self.buttons.values():
            b.setCollapsed(self._collapsed)

    # Overview and Settings can't be hidden (you need a home and a way back).
    ALWAYS = {"overview", "settings"}
    HIDEABLE = [("analytics", "Analytics"), ("subscriptions", "Subscriptions"),
                ("goals", "Goals"), ("history", "History")]

    def apply_hidden(self, hidden):
        hidden = set(hidden or [])
        for k, b in self.buttons.items():
            b.setVisible(k in self.ALWAYS or k not in hidden)

    def add_module_nav(self, key, icon, text):
        """Append a sidebar button for a user module (above Settings)."""
        b = NavButton(key, icon, text)
        b.clicked.connect(self.navigated.emit)
        self.buttons[key] = b
        self._lay.insertWidget(self._lay.count() - 2, b)   # before stretch + Settings
        return b

    def setActive(self, key):
        for k, b in self.buttons.items():
            b.setActive(k == key)


# --------------------------------------------------------------------------- #
#  Top bar with month navigation
# --------------------------------------------------------------------------- #
class IconButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon, size=28, isz=14, color=T.TEXT_MUTED):
        super().__init__()
        self.icon, self.isz, self._color = icon, isz, color
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def enterEvent(self, e): self._hover = True; self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def focusInEvent(self, e):  super().focusInEvent(e);  self.update()
    def focusOutEvent(self, e): super().focusOutEvent(e); self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = T.TEXT if self._hover else self._color
        m = (self.width() - self.isz) / 2
        icons.draw(p, self.icon, QRectF(m, m, self.isz, self.isz), col, 1.6)
        draw_focus_ring(self, p)


class MonthPickerPopup(QFrame):
    """Floating month-grid picker: year nav header + 4×3 month buttons."""
    selected = pyqtSignal(int, int)   # (year, month)

    _MONS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def __init__(self, available: set, today: date,
                 cur_year: int, cur_month: int, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("MonthPicker")
        self.setStyleSheet(f"""
            MonthPickerPopup {{
                background:{T.BG_CARD};
                border:1px solid {T.BORDER};
                border-radius:{T.RADIUS}px;
            }}
        """)
        self._available = available
        self._today = today
        self._cur = (cur_year, cur_month)
        self._pick_year = cur_year

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        # Year navigation row
        yr_row = QHBoxLayout(); yr_row.setContentsMargins(0, 0, 0, 0); yr_row.setSpacing(4)
        self._yr_prev = IconButton("chevron_left", 22, 11)
        self._yr_prev.setToolTip("Previous year")
        self._yr_prev.clicked.connect(lambda: self._shift_year(-1))
        self._yr_lbl = label("", T.TEXT, 12, bold=True)
        self._yr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._yr_next = IconButton("chevron_right", 22, 11)
        self._yr_next.setToolTip("Next year")
        self._yr_next.clicked.connect(lambda: self._shift_year(1))
        yr_row.addWidget(self._yr_prev)
        yr_row.addStretch(1)
        yr_row.addWidget(self._yr_lbl)
        yr_row.addStretch(1)
        yr_row.addWidget(self._yr_next)
        lay.addLayout(yr_row)

        self._grid_w = QWidget()
        self._grid = QGridLayout(self._grid_w)
        self._grid.setSpacing(4)
        self._grid.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._grid_w)

        self._rebuild()

    def _shift_year(self, d: int):
        self._pick_year += d
        self._rebuild()

    def _rebuild(self):
        while self._grid.count():
            it = self._grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        self._yr_lbl.setText(str(self._pick_year))
        y = self._pick_year
        for i, name in enumerate(self._MONS):
            m = i + 1
            row, col = divmod(i, 4)
            is_cur   = (y, m) == self._cur
            is_today = (y == self._today.year and m == self._today.month)
            has_data = (y, m) in self._available

            btn = QPushButton(name)
            btn.setFixedSize(54, 28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFlat(True)

            if is_cur:
                bg, fg, brd = T.ACCENT, T.ON_ACCENT, T.ACCENT
            elif has_data:
                bg, fg, brd = T.BG_CARD_SOFT, T.TEXT, T.BORDER
            else:
                bg, fg, brd = "transparent", T.TEXT_DIM, "transparent"

            today_rule = f"border-bottom:2px solid {T.GREEN};" if is_today and not is_cur else ""
            bold_w = "bold" if is_cur or has_data else "normal"

            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{bg}; color:{fg};
                    border:1px solid {brd}; {today_rule}
                    border-radius:4px;
                    font-family:{T.FONT_FAMILY}; font-size:11px; font-weight:{bold_w};
                }}
                QPushButton:hover {{
                    background:{T.BG_HOVER}; color:{T.TEXT};
                    border:1px solid {T.ACCENT};
                }}
            """)
            btn.clicked.connect(lambda _, yy=y, mm=m: self._pick(yy, mm))
            self._grid.addWidget(btn, row, col)

    def _pick(self, year: int, month: int):
        self.selected.emit(year, month)
        self.close()


class MonthNav(QWidget):
    prev  = pyqtSignal()
    next  = pyqtSignal()
    today = pyqtSignal()
    jump  = pyqtSignal(int, int)   # (year, month) — direct jump from picker

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._available: set   = set()
        self._today_date: date = date.today()
        self._cur_year:  int   = self._today_date.year
        self._cur_month: int   = self._today_date.month

        today_btn = IconButton("today", 26, 13)
        today_btn.setToolTip("Go to today")
        today_btn.clicked.connect(self.today.emit)
        bl = IconButton("chevron_left", 26, 12)
        bl.setToolTip("Previous period")
        bl.clicked.connect(self.prev.emit)

        self.lbl = QPushButton("—")
        lf = QFont(T.FONT_FAMILY); lf.setPixelSize(T.scaled(12)); lf.setBold(True)
        self.lbl.setFont(lf)
        self.lbl.setFixedWidth(148)
        self.lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._style_lbl()
        self.lbl.clicked.connect(self._show_picker)

        br = IconButton("chevron_right", 26, 12)
        br.setToolTip("Next period")
        br.clicked.connect(self.next.emit)

        lay.addWidget(today_btn); lay.addWidget(bl)
        lay.addWidget(self.lbl); lay.addWidget(br)

    def _style_lbl(self):
        self.lbl.setStyleSheet(
            f"QPushButton{{color:{T.TEXT}; background:{T.BG_CARD}; border:1px solid {T.BORDER};"
            f"padding:5px 0; letter-spacing:1px;}}"
            f"QPushButton:hover{{border-color:{T.ACCENT}; color:{T.TEXT};}}")

    def set_label(self, text):
        self.lbl.setText(text)

    def set_context(self, available: set, today: date, cur_year: int, cur_month: int):
        """Update the picker's knowledge of available months and current position."""
        self._available  = available
        self._today_date = today
        self._cur_year   = cur_year
        self._cur_month  = cur_month

    def _show_picker(self):
        popup = MonthPickerPopup(
            self._available, self._today_date,
            self._cur_year, self._cur_month)
        popup.selected.connect(self.jump.emit)
        pos = self.lbl.mapToGlobal(self.lbl.rect().bottomLeft())
        pos.setX(pos.x() - 40)   # nudge left so grid is roughly centred under the label
        popup.move(pos)
        popup.show()


class TopBar(QWidget):
    prev  = pyqtSignal()
    next  = pyqtSignal()
    today = pyqtSignal()
    jump  = pyqtSignal(int, int)      # (year, month) — from month-picker
    search        = pyqtSignal()      # open global search
    mode_changed  = pyqtSignal(str)   # "month" | "week"

    def __init__(self):
        super().__init__()
        self.setFixedHeight(T.HEADER_H)
        self.setStyleSheet(
            f"background:{T.BG_HEADER}; border-bottom:1px solid {T.BORDER_SOFT};")
        # The header's contents ride the same centred column as the page body, so
        # the title lands on the content's left edge and the search button on its
        # right edge instead of floating against the window frame while the body
        # sits 170px inboard of them.
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)

        self.title = label("Overview", T.TEXT, T.FS_HEAD, bold=True)
        self.modebar = SegTabBar(["Month", "Week"], 0, kind="pill")
        self.modebar.changed.connect(lambda m: self.mode_changed.emit(m.lower()))
        self.nav = MonthNav()
        self.nav.prev.connect(self.prev.emit)
        self.nav.next.connect(self.next.emit)
        self.nav.today.connect(self.today.emit)
        self.nav.jump.connect(self.jump.emit)

        center = QWidget()
        cl = QHBoxLayout(center); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(12)
        cl.addWidget(self.modebar); cl.addWidget(self.nav)
        self._center = center

        self.search_btn = IconButton("search", 28, 15)
        self.search_btn.setToolTip("Search (everything)")
        self.search_btn.clicked.connect(self.search.emit)

        lay.addWidget(self.title)
        lay.addStretch(1)
        lay.addWidget(center)
        lay.addStretch(1)
        lay.addWidget(self.search_btn)
        outer.addWidget(bounded(row, T.CONTENT_MAX_W))

    def set_controls_visible(self, mode: bool, nav: bool):
        """Show/hide the Month|Week pill and the date navigation arrow block."""
        self.modebar.setVisible(mode)
        self.nav.setVisible(nav)
        self._center.setVisible(mode or nav)

    def set_title(self, text): self.title.setText(text)
    def set_month(self, text): self.nav.set_label(text)
    def set_mode(self, mode): self.modebar.set_active(mode.capitalize())
    def set_nav_context(self, available: set, today: date, cur_year: int, cur_month: int):
        self.nav.set_context(available, today, cur_year, cur_month)


# --------------------------------------------------------------------------- #
#  Segmented tab bar (two visual styles)
# --------------------------------------------------------------------------- #
class SegTabBar(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, items, active=0, kind="tab"):
        super().__init__()
        self.kind = kind
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3) if kind == "pill" else \
            lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3 if kind == "pill" else 18)

        if kind == "pill":
            self.setStyleSheet(
                f"SegTabBar {{ background:{T.BG_CARD_SOFT};"
                f"border:1px solid {T.BORDER}; }}")

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._btns = []
        for i, name in enumerate(items):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            bf = QFont(T.FONT_FAMILY); bf.setPixelSize(T.scaled(11)); bf.setBold(kind == "pill")
            b.setFont(bf)
            self._style(b)
            if i == active:
                b.setChecked(True)
            b.clicked.connect(lambda _=False, n=name: self.changed.emit(n))
            self.group.addButton(b)
            self._btns.append(b)
            lay.addWidget(b)
        if kind == "tab":
            lay.addStretch(1)

    def _style(self, b):
        if self.kind == "pill":
            b.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{T.TEXT_MUTED};
                    border:none; padding:5px 13px; }}
                QPushButton:hover {{ color:{T.TEXT}; }}
                QPushButton:checked {{ background:{T.BG_PILL}; color:{T.TEXT}; }}""")
        else:
            b.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{T.TEXT_MUTED};
                    border:none; padding:7px 1px 8px 1px;
                    border-bottom:2px solid transparent; }}
                QPushButton:hover {{ color:{T.TEXT}; }}
                QPushButton:checked {{ color:{T.TEXT};
                    border-bottom:2px solid {T.ACCENT}; }}""")

    def set_active(self, name):
        """Check the button with this label without emitting `changed`."""
        for b in self._btns:
            if b.text() == name:
                b.setChecked(True)


# --------------------------------------------------------------------------- #
#  Ledger (Incoming / Outgoing) card
# --------------------------------------------------------------------------- #
def calc_eval(text):
    """Evaluate a tiny arithmetic expression (e.g. '10*12'); None if invalid."""
    s = re.sub(r"[^0-9+\-*/.() ]", "", str(text))
    if not s.strip():
        return None
    try:
        v = eval(s, {"__builtins__": {}}, {})       # input is sanitised above
    except Exception:
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return round(float(v), 2)
    return None


def _dot_icon(color, size=14):
    pm = QPixmap(size, size); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if color:
        p.setBrush(QColor(color)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(3, 3, size - 6, size - 6)
    else:
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.TEXT_DIM), 1.3))
        p.drawRect(3, 3, size - 6, size - 6)
    p.end()
    return QIcon(pm)


class InlineEdit(QLineEdit):
    """A QLineEdit that commits on Enter / focus-out and cancels on Esc. An
    optional on_tab callback lets Tab commit-and-advance to another field
    (e.g. a new item's name -> amount) instead of just closing the editor."""
    def __init__(self, text, on_commit, on_cancel, right=False, px=13, on_tab=None):
        super().__init__(str(text))
        self._done = False
        self._on_commit = on_commit
        self._on_cancel = on_cancel
        self._on_tab = on_tab
        f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(px)); self.setFont(f)
        if right:
            self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(
            f"QLineEdit{{background:{T.BG_APP}; border:1px solid {T.ACCENT};"
            f"padding:1px 5px; color:{T.TEXT};}}")
        self.returnPressed.connect(self._commit)
        self.editingFinished.connect(self._commit)
        QTimer.singleShot(0, self._grab)

    def _grab(self):
        self.setFocus(); self.selectAll()

    def _commit(self):
        if self._done:
            return
        self._done = True
        self._on_commit(self.text())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._done = True
            self._on_cancel()
            return
        super().keyPressEvent(e)

    def focusNextPrevChild(self, next):
        # Forward-Tab with an advance handler: commit-and-advance instead of
        # letting Qt's default tab-order traversal just close the editor.
        if next and self._on_tab is not None and not self._done:
            self._done = True
            self._on_tab(self.text())
            return False
        return super().focusNextPrevChild(next)


class RowIcon(QWidget):
    """A single ledger-row action, drawn as one of the custom vector glyphs
    (icons.py) rather than a borrowed Unicode character.

    Three visual states, so the same control both invites an action and reports
    a state:
      · rest      — T.TEXT_DIM, the quiet default
      · hover      — ``hover`` colour, on direct mouse-over or keyboard focus
      · lit       — ``on_color`` when the underlying property is set (a note
                    exists, recurrence is active); a lit icon stays visible even
                    when the row isn't hovered, because it's now status, not just
                    an affordance.

    Rows hide the un-lit icons until the row is hovered (see CategoryRow); a lit
    icon opts out of that hiding via ``is_lit``.
    """
    clicked = pyqtSignal()

    def __init__(self, name, tooltip, on_color=None, hover=None):
        super().__init__()
        self.name = name
        self._on_color = on_color
        self._hover_col = hover or T.ACCENT
        self._lit = False
        self._hover = False
        self.setFixedSize(ROW_ICON, ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setToolTip(tooltip)

    @property
    def is_lit(self):
        return self._lit

    def set_lit(self, lit):
        self._lit = bool(lit)
        self.update()

    def enterEvent(self, e): self._hover = True; self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def focusInEvent(self, e):  super().focusInEvent(e);  self.update()
    def focusOutEvent(self, e): super().focusOutEvent(e); self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        if self._hover or self.hasFocus():
            col = self._hover_col
        elif self._lit and self._on_color:
            col = self._on_color
        else:
            col = T.TEXT_DIM
        isz = ROW_ICON - 4
        m = (self.width() - isz) / 2
        icons.draw(p, self.name, QRectF(m, (self.height() - isz) / 2, isz, isz),
                   col, 1.4)
        draw_focus_ring(self, p)


class PriorityCell(QWidget):
    """The 'hidden dropdown' priority control: a dot that opens a menu on click.
    Blank when unset, unless the row is hovered."""
    def __init__(self, node, card):
        super().__init__()
        self.node, self.card = node, card
        self._hover = False
        self.setFixedWidth(W_PR)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Set priority")

    def set_hover(self, v):
        if self._hover != v:
            self._hover = v
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        col = PRIO_COLORS.get(self.node.get("priority", 0) or 0)
        s = 8.0
        rect = QRectF((self.width() - s) / 2, (self.height() - s) / 2, s, s)
        if col:
            p.setBrush(QColor(col)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(rect)
        elif self._hover:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(T.TEXT_DIM), 1.2))
            p.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.card._open_priority(self.node,
                                     self.mapToGlobal(self.rect().bottomLeft()))


class CategoryRow(QWidget):
    """A single ledger row.

    - Parent name click → expand/collapse children.
    - Leaf name and amount are click-to-edit inline.
    - Due date always clickable (calendar picker).
    - ✕ delete and + add-child always visible (dim at rest, brighten on
      direct hover) — not hidden until the row is moused over, so the
      affordance is discoverable at a glance.
    """
    def __init__(self, card, node, kind, depth=0, active=True):
        super().__init__()
        self.card = card
        self.node = node
        self._pcell = None
        self._row_icons = []          # RowIcons that hide at rest, show on hover
        self.setObjectName("Row")
        self.setFixedHeight(ROW_H)
        self.setStyleSheet(f"#Row:hover{{background:{T.BG_HOVER};}}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(PAD_L, 0, PAD_R, 0)
        lay.setSpacing(6)

        cur        = card.currency
        income     = kind == "income"
        has_kids   = bool(node.get("children"))
        expandable = has_kids or node.get("expandable")
        leaf       = not has_kids
        editing    = card._editing

        if depth:
            lay.addSpacing(depth * INDENT)

        # ── left "+" : add an indented sub-item (hover-revealed) ───────── #
        plus_cell = QWidget(); plus_cell.setFixedWidth(PLUS_W)
        pcl = QHBoxLayout(plus_cell); pcl.setContentsMargins(0, 0, 0, 0); pcl.setSpacing(0)
        add_sub = RowIcon("plus_sub", "Add sub-item")
        add_sub.clicked.connect(lambda: card._add_child(node))
        pcl.addWidget(add_sub)
        self._row_icons.append(add_sub)
        lay.addWidget(plus_cell)

        # ── chevron ──────────────────────────────────────────────────── #
        chev = QWidget(); chev.setFixedWidth(CHEV_W)
        cl = QHBoxLayout(chev); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
        if expandable:
            arrow = "▾" if node.get("expanded") else "▸"
            tw = Clickable(arrow, T.TEXT_MUTED, 11, hover=T.TEXT)
            tw.clicked.connect(lambda: card._toggle(node))
            cl.addWidget(tw)
        elif depth:
            cl.addWidget(label("└", T.TEXT_DIM, 11))
        lay.addWidget(chev)

        # ── name ─────────────────────────────────────────────────────── #
        nm_col = (T.TEXT if depth == 0 else T.TEXT_MUTED) if active else T.TEXT_DIM
        if editing == (node["id"], "name"):
            ie = InlineEdit(
                node["name"], lambda v: card._commit(node, "name", v), card._cancel,
                on_tab=(lambda v: card._commit(node, "name", v, advance_to="amount"))
                       if leaf else None)
            ie.setMinimumWidth(60)
            lay.addWidget(ie, 1)
        else:
            # A leaf name is click-to-edit (editable underline); a parent name
            # toggles children (a link, not a field) so it stays a pointer.
            nm = Clickable(node["name"], nm_col, 13, hover=T.TEXT,
                           editable=not expandable)
            if expandable:
                nm.clicked.connect(lambda: card._toggle(node))
            else:
                nm.clicked.connect(lambda: card._start(node, "name"))
            lay.addWidget(nm)
            # Tag *chips* stay by the name — they're content (what this item is
            # tagged), not an action. The edit-tags / recurrence / note / delete
            # glyphs moved out to the trailing action column (see below).
            for t in (node.get("tags") or [])[:4]:
                lay.addWidget(tag_chip(t, on_click=lambda t=t: card._filter_tag(t)))
            lay.addStretch(1)

        # ── amount (parents show whitespace — value lives in children) ── #
        if not leaf:
            ph_amt = QWidget(); ph_amt.setFixedWidth(W_AMOUNT); lay.addWidget(ph_amt)
        else:
            amt  = B.node_amount(node)
            col  = (T.GREEN if income else T.RED) if active else T.TEXT_DIM
            disp = money(amt if income else -amt, cur)
            if editing == (node["id"], "amount"):
                shown = int(amt) if float(amt).is_integer() else amt
                ie = InlineEdit(shown, lambda v: card._commit(node, "amount", v),
                                card._cancel, right=True)
                ie.setFixedWidth(W_AMOUNT)
                lay.addWidget(ie)
            else:
                a = Clickable(disp, col, 13, bold=True, hover=col, editable=True)
                if not active:
                    a.setToolTip("Not due this month — excluded from P&L")
                a.clicked.connect(lambda: card._start(node, "amount"))
                a.setFixedWidth(W_AMOUNT)
                a.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                lay.addWidget(a)

        # ── expense-only: paid toggle + due date + priority ──────────── #
        if not income:
            if leaf:
                paid = bool(node.get("paid"))
                overdue = (not paid) and _is_overdue(node.get("due"), card.today)
                pd = Clickable("✔" if paid else "○",
                               T.GREEN if paid else (T.RED if overdue else T.TEXT_DIM),
                               12, hover=T.GREEN)
                pd.setToolTip("Paid — click to undo" if paid else "Mark paid")
                pd.setFixedWidth(W_PAID)
                pd.clicked.connect(lambda: card._toggle_paid(node))
                lay.addWidget(pd)

                has_due = bool(node.get("due"))
                due_col = T.GREEN if paid else (T.RED if overdue
                                                else (T.TEXT if has_due else T.TEXT_DIM))
                d = Clickable(due_display(node.get("due")), due_col, 11, hover=T.TEXT)
                d.setToolTip("Overdue" if overdue else "Due date — click to pick")
                d.setFixedWidth(W_DUE)
                d.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                d.clicked.connect(lambda: card._open_calendar(node, QCursor.pos()))
                lay.addWidget(d)
                self._pcell = PriorityCell(node, card)
                lay.addWidget(self._pcell)
            else:
                ph_pd  = QWidget(); ph_pd.setFixedWidth(W_PAID); lay.addWidget(ph_pd)
                ph_due = QWidget(); ph_due.setFixedWidth(W_DUE); lay.addWidget(ph_due)
                ph_pr  = QWidget(); ph_pr.setFixedWidth(W_PR);  lay.addWidget(ph_pr)

        # ── added (read-only; parents show whitespace) ───────────────── #
        if leaf:
            added = label(node.get("added") or "—", T.TEXT_DIM, 11)
            added.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            added = QWidget()
        added.setFixedWidth(W_ADDED)
        lay.addWidget(added)

        # ── action column: recurrence · tag · note · delete ──────────── #
        # One right-aligned group instead of glyphs scattered along the row.
        # Everything here is hover-revealed, EXCEPT an icon that's "lit" because
        # its property is set (an active recurrence, an existing note) — a lit
        # icon stays visible at rest as a status marker. Right-aligned so the
        # group hugs the row's edge no matter which optional icons are present.
        act = QWidget(); act.setFixedWidth(W_ACT)
        al  = QHBoxLayout(act); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(3)
        al.addStretch(1)

        if leaf:
            on = bool(node.get("_recur", node.get("recurring")))
            rc = RowIcon("recurring",
                         repeat_label(node.get("_recur_repeat") or node.get("repeat"))
                         or "Set recurrence",
                         on_color=T.TEXT)
            rc.set_lit(on)
            rc.clicked.connect(lambda: card._open_repeat(node))
            al.addWidget(rc); self._row_icons.append(rc)

        tg = RowIcon("tag", "Edit tags")
        tg.clicked.connect(lambda: card._open_tags(node))
        al.addWidget(tg); self._row_icons.append(tg)

        if leaf:
            has_note = bool((node.get("note") or "").strip())
            nt = RowIcon("note", node.get("note") if has_note else "Add note",
                         on_color=T.ACCENT)
            nt.set_lit(has_note)
            nt.clicked.connect(lambda: card._open_note(node))
            al.addWidget(nt); self._row_icons.append(nt)

        x = RowIcon("trash", "Delete", hover=T.RED)
        x.clicked.connect(lambda: card._delete(node))
        al.addWidget(x); self._row_icons.append(x)

        lay.addWidget(act)

        # Initial visibility: only lit icons show at rest; the rest wait for hover.
        for ic in self._row_icons:
            ic.setVisible(ic.is_lit)

    def enterEvent(self, e):
        for ic in self._row_icons:
            ic.setVisible(True)
        if self._pcell:
            self._pcell.set_hover(True)

    def leaveEvent(self, e):
        for ic in self._row_icons:
            ic.setVisible(ic.is_lit)
        if self._pcell:
            self._pcell.set_hover(False)


class LedgerCard(QFrame):
    changed          = pyqtSignal()
    delete_recurring = pyqtSignal(str, str, str)  # (name, kind, scope)

    def __init__(self, kind, doc, today, currency="$"):
        super().__init__()
        self.kind = kind
        self.doc = doc
        self.today = today
        self.currency = currency
        self.sort_mode = "By Due" if kind != "income" else "Custom"
        self.week_mode: int | None = None    # legacy; unused under the flat store
        self._editing = None                 # (node_id, field) or None
        self.store = None                    # ItemStore — when set, edits persist there
        self.tag_filter = None               # show only rows carrying this tag
        self._just_added_id = None           # node id to fade in on next rebuild

        self.setObjectName("Card")
        # Fill and surrounding border dropped with every other block; the 2px top
        # rule stays because here it is *functional*, not decorative — green vs
        # red is the income/expense distinction this card exists to make, the
        # same signal as the ▲/▼ and the sign on every amount below it. That's
        # the opposite of the T.ACCENT rule removed from card(), which used the
        # income colour to mean "important" and landed above an expense chart.
        accent = T.GREEN if kind == "income" else T.RED
        self.setStyleSheet(
            f"#Card{{background:transparent; border:none;"
            f"border-top:2px solid {accent};}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 14, 0, 8)
        root.setSpacing(0)
        income = kind == "income"
        tri_col = T.GREEN if income else T.RED

        # ---- header: title + total + column labels ----------------------- #
        head = QHBoxLayout()
        head.setContentsMargins(PAD_L, 0, PAD_R, 0); head.setSpacing(6)
        head.addWidget(label("▲" if income else "▼", tri_col, 10))
        head.addWidget(label("Incoming" if income else "Outgoing", T.TEXT, 14, bold=True))
        self._overflow = Clickable("⋯", T.TEXT_DIM, 15, hover=T.TEXT)
        self._overflow.setToolTip("More…")
        self._overflow.clicked.connect(self._open_overflow)
        head.addSpacing(4)
        head.addWidget(self._overflow)
        head.addStretch(1)
        self.total_lbl = label("", tri_col, 14, bold=True,
                               align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_lbl.setFixedWidth(W_AMOUNT)
        head.addWidget(self.total_lbl)
        if not income:
            paid_h = label("✔", T.TEXT_DIM, 9, align=Qt.AlignmentFlag.AlignCenter)
            paid_h.setFixedWidth(W_PAID); head.addWidget(paid_h)
            due_h = label("Due", T.TEXT_DIM, 9,
                          align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            due_h.setFixedWidth(W_DUE); head.addWidget(due_h)
            pr_h = label("Pr", T.TEXT_DIM, 9, align=Qt.AlignmentFlag.AlignCenter)
            pr_h.setToolTip("Priority")   # the column is too narrow for the word;
            pr_h.setFixedWidth(W_PR); head.addWidget(pr_h)   # tooltip carries it
        added_h = label("Added", T.TEXT_DIM, 9,
                        align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        added_h.setFixedWidth(W_ADDED); head.addWidget(added_h)
        gap = QWidget(); gap.setFixedWidth(W_ACT); head.addWidget(gap)
        root.addLayout(head)
        root.addSpacing(6)

        # ---- sort tabs -------------------------------------------------- #
        tabs_host = QWidget()
        th = QHBoxLayout(tabs_host)
        th.setContentsMargins(PAD_L, 0, PAD_R, 0); th.setSpacing(0)
        self.tabbar = SegTabBar(
            ["Custom", "By Due", "By Added"] if not income else ["Custom", "By Added"],
            1 if not income else 0, kind="tab")
        self.tabbar.changed.connect(self._set_sort)
        th.addWidget(self.tabbar)
        root.addWidget(tabs_host)
        root.addWidget(hsep())

        # ---- scrolling list --------------------------------------------- #
        self.list_box = QVBoxLayout()
        self.list_box.setContentsMargins(0, 4, 0, 0)
        self.list_box.setSpacing(1)
        self._holder = QWidget(); self._holder.setLayout(self.list_box)
        self._holder.setStyleSheet("background:transparent;")
        self._scroll = BoundedScroll(); self._scroll.setWidget(self._holder)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background:transparent; border:none;")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._scroll, 1)

        self.rebuild()

    # -- data ------------------------------------------------------------- #
    def nodes(self):
        return self.doc["income" if self.kind == "income" else "expenses"]

    def set_week_mode(self, week_idx: int | None):
        """Switch to a specific week-of-month view (expenses only). None = month view."""
        self.week_mode = week_idx
        self.rebuild()

    def _week_range(self):
        """(start, end) dates for self.week_mode, or (None, None) if not in week mode."""
        if self.week_mode is None:
            return None, None
        y, m = self._cur_ym()
        n_weeks = int(self.doc.get("weeks", 4))
        ranges = B.month_week_ranges(y, m, n_weeks)
        if self.week_mode > len(ranges):
            return None, None
        _, start, end = ranges[self.week_mode - 1]
        return start, end

    def _in_week(self, node, start, end) -> bool:
        """True if the node's added date (day-of-month) falls within the week."""
        import calendar as _cal
        y, m = self._cur_ym()
        added = node.get("added")
        if added:
            try:
                day = int(str(added).split("-")[-1])
                day = min(day, _cal.monthrange(y, m)[1])
                from datetime import date as _d
                return start <= _d(y, m, day) <= end
            except (ValueError, IndexError):
                pass
        return False

    def list_hint(self) -> int:
        """Natural pixel height of the row list (used to equalise two cards)."""
        return self._holder.sizeHint().height()

    def set_list_height(self, h: int):
        self._scroll.setFixedHeight(int(h))

    def set_doc(self, doc):
        self.doc = doc
        self.currency = doc.get("currency", "$")
        self.rebuild()

    def _set_sort(self, mode):
        self.sort_mode = mode
        self.rebuild()

    def _filter_tag(self, tag):
        """Toggle a tag filter on this ledger (click a chip to set, again to clear)."""
        self.tag_filter = None if self.tag_filter == tag else tag
        self.rebuild()

    def _has_tag(self, node, tag):
        if tag in (node.get("tags") or []):
            return True
        return any(self._has_tag(c, tag) for c in (node.get("children") or []))

    def _sorted(self, nodes):
        if self.sort_mode == "By Added":
            return sorted(nodes, key=lambda n: n.get("added") or "99-99")
        if self.sort_mode == "By Due":
            return sorted(nodes, key=lambda n: n.get("due") or "99-99")
        return nodes

    # -- build ------------------------------------------------------------ #
    def rebuild(self):
        self._year, self._month = self._cur_ym()
        y, m = self._year, self._month
        while self.list_box.count():
            it = self.list_box.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.deleteLater()

        if self.tag_filter:
            fb = Clickable(f"Filtered by #{self.tag_filter}   ·   ✕ clear",
                           T.ACCENT, 11, hover=T.TEXT)
            fb.setContentsMargins(PAD_L + CHEV_W, 0, 0, 6)
            fb.clicked.connect(lambda _=False: self._filter_tag(self.tag_filter))
            self.list_box.addWidget(fb)

        week_start, week_end = self._week_range()
        week_filtering = week_start is not None

        for node in self._sorted(self.nodes()):
            if self.tag_filter and not self._has_tag(node, self.tag_filter):
                continue
            if week_filtering:
                if node.get("children"):
                    kids = [ch for ch in self._sorted(node["children"])
                            if self._in_week(ch, week_start, week_end)]
                    if not kids:
                        continue
                    self._add_row(node, 0, True)
                    if node.get("expanded"):
                        for ch in kids:
                            self._add_row(ch, 1, B.fires_in(ch.get("repeat"), y, m))
                else:
                    if not self._in_week(node, week_start, week_end):
                        continue
                    self._add_row(node, 0, B.fires_in(node.get("repeat"), y, m))
            else:
                leaf = not node.get("children")
                active = (not leaf) or B.fires_in(node.get("repeat"), y, m)
                self._add_row(node, 0, active)
                if node.get("expanded"):
                    if node.get("children"):
                        for ch in self._sorted(node["children"]):
                            self._add_row(ch, 1, B.fires_in(ch.get("repeat"), y, m))
                    else:
                        add = Clickable("+ sub-item", T.TEXT_DIM, 11, hover=T.ACCENT)
                        add.setContentsMargins(PAD_L + INDENT + CHEV_W, 0, 0, 0)
                        add.clicked.connect(lambda _=False, p=node: self._add_child(p))
                        self.list_box.addWidget(add)

        more = Clickable("+ Add item", T.TEXT_DIM, 12, hover=T.ACCENT)
        more.setContentsMargins(PAD_L + CHEV_W, 6, 0, 0)
        more.clicked.connect(self._add_top)
        self.list_box.addWidget(more)
        self.list_box.addStretch(1)

        if week_filtering:
            # total = only items in this week
            week_total = sum(
                float(n.get("amount", 0))
                for n in self.nodes()
                if not n.get("children") and self._in_week(n, week_start, week_end)
            )
            sign = 1 if self.kind == "income" else -1
            self.total_lbl.setText(money(week_total * sign, self.currency))
        else:
            self.total_lbl.setText(
                money(B.active_total(self.nodes(), y, m) * (1 if self.kind == "income" else -1),
                      self.currency))

    def _add_row(self, node, depth, active=True):
        row = CategoryRow(self, node, self.kind, depth, active)
        self.list_box.addWidget(row)
        if self._just_added_id is not None and node.get("id") == self._just_added_id:
            _row_fade_in(row)
            self._just_added_id = None

    # -- search navigation: scroll to + call out a specific row ----------- #
    def _find_row_widget(self, node_id):
        for i in range(self.list_box.count()):
            w = self.list_box.itemAt(i).widget()
            if isinstance(w, CategoryRow) and w.node.get("id") == node_id:
                return w
        return None

    def _find_parent_with_child(self, node_id):
        for n in self.nodes():
            for ch in (n.get("children") or []):
                if ch.get("id") == node_id:
                    return n
        return None

    def flash_row(self, node_id: str):
        """Scroll to and briefly highlight the row for node_id — called when
        search navigation lands here so the found item isn't a needle hunt."""
        row = self._find_row_widget(node_id)
        if row is None:
            parent = self._find_parent_with_child(node_id)
            if parent is not None and not parent.get("expanded"):
                if self.store:
                    self.store.set_expanded(self._def_of(parent), True)
                else:
                    parent["expanded"] = True
                self.rebuild()
                row = self._find_row_widget(node_id)
        if row is None:
            return
        self._scroll.ensureWidgetVisible(row, 0, 60)
        flash_widget(row, revert_style=f"#Row:hover{{background:{T.BG_HOVER};}}")

    def _cur_ym(self):
        y, m = self.doc.get("month", "2026-01").split("-")
        return int(y), int(m)

    # -- flat-store helpers ---------------------------------------------- #
    def _item_type(self):
        return "income" if self.kind == "income" else "expense"

    def _range_start_iso(self):
        rs = self.doc.get("range_start")
        if rs:
            return rs
        y, m = self._cur_ym()
        return f"{y:04d}-{m:02d}-01"

    def _occ_of(self, node):
        return node.get("_occ")

    def _def_of(self, node):
        return node.get("_def_id") or node.get("id")

    def _open_overflow(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{T.BG_CARD}; border:1px solid {T.BORDER_LIGHT};"
            f"padding:6px;}} QMenu::item{{padding:6px 18px; border-radius:{T.RADIUS}px;}}"
            f"QMenu::item:selected{{background:{T.BG_HOVER};}}"
            f"QMenu::separator{{height:1px; background:{T.BORDER}; margin:4px 2px;}}")
        parents = [n for n in self.nodes() if n.get("children")]
        if parents:
            if any(not n.get("expanded") for n in parents):
                exp = menu.addAction("Expand all")
                exp.triggered.connect(lambda: self._set_all_expanded(True))
            if any(n.get("expanded") for n in parents):
                col = menu.addAction("Collapse all")
                col.triggered.connect(lambda: self._set_all_expanded(False))
            menu.addSeparator()
        act = menu.addAction("Clear all…")
        act.triggered.connect(self._clear_all)
        menu.exec(self._overflow.mapToGlobal(
            self._overflow.rect().bottomLeft()))

    # -- mutations -------------------------------------------------------- #
    def _toggle(self, node):
        if self.store:
            self.store.set_expanded(self._def_of(node), not node.get("expanded"))
            self.changed.emit()
            return
        node["expanded"] = not node.get("expanded")
        self.rebuild()
        self.changed.emit()

    def _set_all_expanded(self, value: bool):
        parents = [n for n in self.nodes() if n.get("children")]
        if self.store:
            for n in parents:
                self.store.set_expanded(self._def_of(n), value)
            self.changed.emit()
            return
        for n in parents:
            n["expanded"] = value
        self.rebuild()
        self.changed.emit()

    # -- bulk clear ------------------------------------------------------- #
    def _clear_all(self):
        reply = QMessageBox.question(
            self, "Clear", f"Remove all items from this list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._editing = None
        if self.store:
            self.store.clear_type(self._item_type())
            self.changed.emit()
            return
        self.nodes().clear()
        self.rebuild()
        self.changed.emit()

    # -- inline editing --------------------------------------------------- #
    def _start(self, node, field):
        self._editing = (node["id"], field)
        self.rebuild()

    def _cancel(self):
        if self._editing is not None:
            self._editing = None
            self.rebuild()

    def _reject_edit(self, message):
        """Revert an inline edit and tell the user why it was rejected."""
        from PyQt6.QtWidgets import QToolTip
        QToolTip.showText(QCursor.pos(), message, self)
        self.rebuild()

    def _commit(self, node, field, value, advance_to=None):
        self._editing = None
        if field == "name":
            v = value.strip()
            if not v:
                self._reject_edit("Name can't be empty — edit discarded."); return
            if self.store:
                self.store.edit_field(self._def_of(node), self._occ_of(node),
                                      "name", v, scope="all")
                if advance_to:
                    self._editing = (node["id"], advance_to)
                self.changed.emit(); return
            node["name"] = v
        elif field == "amount":
            ev = calc_eval(value)
            if ev is None:
                self._reject_edit(f"Couldn't parse \"{value.strip()}\" as an amount "
                                  "— edit discarded."); return
            if self.store:
                scope = self._resolve_scope(node)
                if scope is None:
                    self.rebuild(); return       # cancelled — discard edit
                self.store.edit_field(self._def_of(node), self._occ_of(node),
                                      "amount", ev, scope=scope)
                self.changed.emit(); return
            node["amount"] = ev
        if advance_to:
            self._editing = (node["id"], advance_to)
        self.rebuild(); self.changed.emit()

    # -- recurrence + due-date popups ------------------------------------- #
    def _open_repeat(self, node):
        changed, value = RepeatDialog.edit(
            self, node.get("_recur_repeat") or node.get("repeat"))
        if not changed:
            return
        if self.store:
            self.store.set_recurrence(self._def_of(node), value)
            self.changed.emit(); return
        # legacy in-doc path
        if value and value.get("type") == "interval" \
                and value.get("unit") in ("month", "year"):
            value["anchor"] = self.doc.get("month")
        node["repeat"] = value
        node["recurring"] = value is not None
        self.rebuild(); self.changed.emit()

    def _open_tags(self, node):
        suggestions = self.store.all_tags() if self.store else []
        changed, tags = TagDialog.edit(self, node.get("tags") or [], suggestions)
        if not changed:
            return
        if self.store:
            self.store.set_tags(self._def_of(node), tags)
            self.changed.emit(); return
        node["tags"] = tags
        self.rebuild(); self.changed.emit()

    def _open_note(self, node):
        changed, text = NoteDialog.edit_note(self, node.get("name", ""),
                                             node.get("note", ""))
        if not changed:
            return
        if self.store:
            self.store.set_note(self._def_of(node), text)
            self.changed.emit(); return
        node["note"] = text
        self.rebuild(); self.changed.emit()

    def _open_calendar(self, node, pos):
        m = QMenu(self)
        m.setStyleSheet(
            f"QMenu{{background:{T.BG_CARD}; border:1px solid {T.BORDER_LIGHT};"
            f"padding:6px;}} QMenu::item{{padding:6px 18px; border-radius:{T.RADIUS}px;}}"
            f"QMenu::item:selected{{background:{T.BG_HOVER};}}"
            f"QMenu::separator{{height:1px; background:{T.BORDER}; margin:4px 2px;}}")
        cal = QCalendarWidget()
        cal.setFixedSize(266, 220)
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setStyleSheet(_calendar_qss())
        # Restrict selectable days to the month being viewed.
        import calendar as _cal
        cy, cmo = self._cur_ym()
        last = _cal.monthrange(cy, cmo)[1]
        cal.setMinimumDate(QDate(cy, cmo, 1))
        cal.setMaximumDate(QDate(cy, cmo, last))
        cal.setCurrentPage(cy, cmo)
        # Month is fixed → hide the prev/next arrows and disable the
        # month/year dropdown buttons so the period can't be changed.
        for _btn_name in ("qt_calendar_prevmonth", "qt_calendar_nextmonth"):
            _b = cal.findChild(QWidget, _btn_name)
            if _b is not None:
                _b.hide()
        for _btn_name in ("qt_calendar_monthbutton", "qt_calendar_yearbutton"):
            _b = cal.findChild(QWidget, _btn_name)
            if _b is not None:
                _b.setEnabled(False)
        qd = self._due_qdate(node.get("due"))
        if qd and qd.isValid():
            cal.setSelectedDate(qd)
        cal.clicked.connect(lambda d: self._pick_due(node, d, m))
        wa = QWidgetAction(m); wa.setDefaultWidget(cal); m.addAction(wa)
        if node.get("due"):
            m.addSeparator()
            m.addAction("Clear date", lambda: self._pick_due(node, None, m))
        m.exec(pos)

    def _pick_due(self, node, qd, menu):
        iso = qd.toString("yyyy-MM-dd") if qd else None
        menu.close()
        if self.store:
            scope = self._resolve_scope(node)
            if scope is None:
                return                            # cancelled
            self.store.edit_field(self._def_of(node), self._occ_of(node),
                                  "due", iso, scope=scope)
            self.changed.emit(); return
        node["due"] = iso
        self.rebuild(); self.changed.emit()

    def _due_qdate(self, due):
        if not due:
            return None
        if len(due) >= 10:
            return QDate.fromString(due, "yyyy-MM-dd")
        parts = due.split("-")
        if len(parts) == 2:
            return QDate(self._year, int(parts[0]), int(parts[1]))
        return None

    def _new_node(self):
        today = date.today()
        n = dm.cat("New item",
                   type=("income" if self.kind == "income" else "expense"),
                   added=today.strftime("%m-%d"))
        if self.kind == "expense":
            start, _ = self._week_range()
            if start is not None:
                n["due"] = start.strftime("%Y-%m-%d")
        return n

    def _add_top(self):
        if self.store:
            defn = self.store.add_top(self._item_type(), self._range_start_iso())
            self._editing = (defn["id"], "name")
            self._just_added_id = defn["id"]
            self.changed.emit(); return
        node = self._new_node()
        self.nodes().append(node)
        self._editing = (node["id"], "name")
        self._just_added_id = node["id"]
        self.rebuild(); self.changed.emit()

    def _add_child(self, parent):
        if self.store:
            child = self.store.add_child(self._def_of(parent), self._item_type(),
                                         self._range_start_iso())
            if child:
                self._editing = (child["id"], "name")
                self._just_added_id = child["id"]
            self.changed.emit(); return
        node = self._new_node()
        parent.setdefault("children", []).append(node)
        parent["expanded"] = True
        self._editing = (node["id"], "name")
        self._just_added_id = node["id"]
        self.rebuild(); self.changed.emit()

    def _open_priority(self, node, pos):
        m = QMenu(self)
        m.setStyleSheet(
            f"QMenu{{background:{T.BG_CARD}; border:1px solid {T.BORDER_LIGHT};"
            f"padding:5px;}} QMenu::item{{padding:6px 24px 6px 8px; border-radius:{T.RADIUS}px;}}"
            f"QMenu::item:selected{{background:{T.BG_HOVER};}}")
        cur = node.get("priority", 0) or 0
        for val in (1, 2, 3, 0):
            act = m.addAction(_dot_icon(PRIO_COLORS.get(val)), PRIO_NAMES[val])
            act.setCheckable(True); act.setChecked(val == cur)
            act.triggered.connect(lambda _=False, v=val: self._set_priority(node, v))
        m.exec(pos)

    def _set_priority(self, node, val):
        if self.store:
            scope = self._resolve_scope(node)
            if scope is None:
                return                            # cancelled
            self.store.edit_field(self._def_of(node), self._occ_of(node),
                                  "priority", val, scope=scope)
            self.changed.emit(); return
        node["priority"] = val
        self.rebuild(); self.changed.emit()

    def _toggle_paid(self, node):
        """Mark this occurrence's bill paid / unpaid (per-occurrence)."""
        if self.store:
            self.store.set_paid(self._def_of(node), self._occ_of(node),
                                not node.get("paid"))
            self.changed.emit(); return
        node["paid"] = not node.get("paid")
        self.rebuild(); self.changed.emit()

    def _is_recurring(self, node) -> bool:
        return bool(node.get("_recur") or node.get("recurring") or node.get("repeat"))

    def _ask_edit_scope(self, node) -> str | None:
        """Ask which occurrences an edit applies to. Returns
        'instance' | 'future' | 'all', or None (cancelled)."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Edit recurring item")
        msg.setText(f'"{node["name"]}" repeats.')
        msg.setInformativeText("Apply this change to:")
        msg.setStyleSheet(f"QMessageBox{{background:{T.BG_CARD};}}")
        b_this   = msg.addButton("This occurrence",  QMessageBox.ButtonRole.AcceptRole)
        b_future = msg.addButton("This + future",    QMessageBox.ButtonRole.AcceptRole)
        b_all    = msg.addButton("All occurrences",  QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is b_this:   return "instance"
        if clicked is b_future: return "future"
        if clicked is b_all:    return "all"
        return None

    def _resolve_scope(self, node) -> str | None:
        """Scope for a field edit: prompt for recurring items; one-offs need no
        prompt (a single occurrence). None means the user cancelled."""
        if not self.store:
            return "instance"               # legacy path ignores scope
        if not self._is_recurring(node):
            return "all"                    # only one occurrence — scope is moot
        if self.store.is_first_occurrence(self._def_of(node), self._occ_of(node)):
            return "all"                    # freshly created — nothing to disambiguate yet
        return self._ask_edit_scope(node)

    def _ask_recurring_scope(self, node) -> str | None:
        """Ask the user which occurrences to delete for a recurring item.
        Returns 'single', 'future', 'all', or None (cancelled)."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete recurring item")
        msg.setText(f'"{node["name"]}" repeats.')
        msg.setInformativeText("Which occurrences do you want to remove?")
        msg.setStyleSheet(f"QMessageBox{{background:{T.BG_CARD};}}")
        btn_once   = msg.addButton("This only",       QMessageBox.ButtonRole.AcceptRole)
        btn_future = msg.addButton("This + future",   QMessageBox.ButtonRole.DestructiveRole)
        btn_all    = msg.addButton("All instances",   QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is btn_once:   return "single"
        if clicked is btn_future: return "future"
        if clicked is btn_all:    return "all"
        return None

    def _delete(self, node):
        is_recurring = bool(node.get("_recur") or node.get("recurring")
                            or node.get("repeat"))
        if is_recurring and self.store and self.store.is_first_occurrence(
                self._def_of(node), self._occ_of(node)):
            is_recurring = False    # freshly created — nothing to disambiguate yet
        if is_recurring:
            scope = self._ask_recurring_scope(node)
            if scope is None:
                return
        else:
            reply = QMessageBox.question(
                self, "Delete", f"Delete \"{node['name']}\"?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            scope = "all" if self.store else "single"

        if self.store:
            self.store.delete_occurrence(self._def_of(node), self._occ_of(node), scope)
            self.changed.emit()
            return

        # legacy in-doc path
        name = node["name"]
        def strip(lst):
            if node in lst:
                lst.remove(node); return True
            return any(strip(n.get("children", [])) for n in lst)
        strip(self.nodes())
        self.rebuild()
        if scope != "single":
            self.delete_recurring.emit(name, self.kind, scope)
        else:
            self.changed.emit()


# --------------------------------------------------------------------------- #
#  Recurrence editor + dark calendar styling
# --------------------------------------------------------------------------- #
def _calendar_qss():
    return f"""
    QCalendarWidget QWidget {{ background:{T.BG_CARD}; color:{T.TEXT}; }}
    QCalendarWidget QAbstractItemView:enabled {{
        background:{T.BG_CARD}; color:{T.TEXT}; outline:none;
        selection-background-color:{T.ACCENT}; selection-color:{T.ON_ACCENT}; }}
    QCalendarWidget QAbstractItemView:disabled {{ color:{T.TEXT_DIM}; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{ background:{T.BG_CARD_SOFT}; }}
    QCalendarWidget QToolButton {{
        background:transparent; color:{T.TEXT}; border:none;
        padding:3px 8px; border-radius:{T.RADIUS}px; }}
    QCalendarWidget QToolButton:hover {{ background:{T.BG_HOVER}; }}
    QCalendarWidget QToolButton::menu-indicator {{ image:none; }}
    QCalendarWidget QSpinBox {{
        background:{T.BG_INPUT}; color:{T.TEXT}; border:1px solid {T.BORDER}; }}
    QCalendarWidget QMenu {{
        background:{T.BG_CARD}; color:{T.TEXT}; border:1px solid {T.BORDER_LIGHT}; }}
    """


# --------------------------------------------------------------------------- #
#  Recurrence editors — laid out like Google Calendar's custom-recurrence
#  dialog ("Repeat every [N] [weeks] on [M]"), while emitting the exact same
#  rule dicts the engine already understands (interval / days).
# --------------------------------------------------------------------------- #
_UNITS = ["day", "week", "month", "year"]
_FREQ_WORD = {"day": "daily", "week": "weekly", "month": "monthly",
              "year": "annually"}


def _freq_summary(every, unit, anchor=None, days=None):
    """Google-style recurrence sentence, e.g. 'Occurs every 2 weeks on Monday'."""
    if days:
        lst = ", ".join(str(d) for d in days)
        return f"Occurs monthly on day{'s' if len(days) > 1 else ''} {lst}"
    head = _FREQ_WORD[unit] if every == 1 else f"every {every} {unit}s"
    out = f"Occurs {head}"
    if anchor is not None:
        if unit == "week":
            out += f" on {anchor.strftime('%A')}"
        elif unit == "month":
            out += f" on day {anchor.day}"
        elif unit == "year":
            out += f" on {anchor.strftime('%d %b')}"
    return out


class WeekdayChips(QWidget):
    """Google-style weekday chip row (Mon-first, matching the heatmap).
    Single-select — the recurrence engine anchors a weekly cycle to one
    start date, so exactly one chip is lit at a time."""
    changed = pyqtSignal(int)    # 0 = Monday … 6 = Sunday

    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(4)
        self._btns = []
        for i, ch in enumerate("MTWTFSS"):
            b = QPushButton(ch); b.setCheckable(True)
            b.setFixedSize(26, 26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{T.BG_INPUT}; color:{T.TEXT_MUTED};"
                f"border:1px solid {T.BORDER}; border-radius:{T.RADIUS}px; font-size:11px;}}"
                f"QPushButton:checked{{background:{T.ACCENT}; color:{T.ON_ACCENT};"
                f"border-color:{T.ACCENT};}}")
            b.clicked.connect(lambda _=False, wd=i: self._pick(wd))
            row.addWidget(b); self._btns.append(b)
        row.addStretch(1)

    def _pick(self, wd):
        self.set_weekday(wd)
        self.changed.emit(wd)

    def set_weekday(self, wd):
        for i, b in enumerate(self._btns):
            b.setChecked(i == wd)


class RepeatDialog(QDialog):
    """Editor for a recurrence rule, Google Calendar style: "Repeat every
    [N] [unit]", plus a monthly-only option to repeat on specific days of
    the month.  Emits the same rule dicts as before (interval / days)."""
    def __init__(self, parent, repeat):
        super().__init__(parent)
        self.setWindowTitle("Recurrence")
        self.setStyleSheet(f"background:{T.BG_CARD};")
        self.setMinimumWidth(300)
        self._result = None
        r = dict(repeat) if repeat else {"type": "interval", "every": 1, "unit": "month"}
        on_days = r.get("type") == "days"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(11)

        # "Repeat every [N] [unit]" — Google Calendar's custom-recurrence row
        self.iv = QWidget()
        ivl = QHBoxLayout(self.iv); ivl.setContentsMargins(0, 0, 0, 0); ivl.setSpacing(8)
        ivl.addWidget(label("Repeat every", T.TEXT, 12))
        self.every = QSpinBox()
        self.every.setRange(1, 99)
        self.every.setFixedWidth(80)
        self.every.setFixedHeight(32)
        self.every.setValue(int(r["every"]) if r.get("type") == "interval" else 1)
        self.every.setStyleSheet(T.input_style("4px 6px") + f"""
            QSpinBox {{ font-size:{T.scaled(13)}px; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width:18px; border:none; background:{T.BG_CARD_SOFT};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background:{T.BG_HOVER};
            }}
            QSpinBox::up-arrow {{
                image:none; border-left:4px solid transparent;
                border-right:4px solid transparent;
                border-bottom:5px solid {T.TEXT_MUTED}; width:0; height:0;
            }}
            QSpinBox::down-arrow {{
                image:none; border-left:4px solid transparent;
                border-right:4px solid transparent;
                border-top:5px solid {T.TEXT_MUTED}; width:0; height:0;
            }}
        """)
        ivl.addWidget(self.every)
        self.unit = QComboBox(); self.unit.addItems(_UNITS)
        self.unit.setCurrentText(r.get("unit", "month")
                                 if r.get("type") == "interval" else "month")
        ivl.addWidget(self.unit); ivl.addStretch(1)
        lay.addWidget(self.iv)

        # monthly-only variant: repeat on specific days of the month
        # (Google's "Monthly on day …", generalised to several days)
        self.btn_days = self._seg("On specific days of month", on_days,
                                  self._sync_ui)

        lay.addWidget(self.btn_days)

        # days-of-month grid
        self.dg = QWidget()
        grid = QGridLayout(self.dg); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(3)
        self.day_btns = {}
        chosen = set(r.get("days", []) if r.get("type") == "days" else [])
        for d in range(1, 32):
            b = QPushButton(str(d)); b.setCheckable(True); b.setChecked(d in chosen)
            b.setFixedSize(30, 24); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{T.BG_INPUT}; color:{T.TEXT_MUTED};"
                f"border:1px solid {T.BORDER}; border-radius:{T.RADIUS}px; font-size:11px;}}"
                f"QPushButton:checked{{background:{T.ACCENT}; color:{T.ON_ACCENT};"
                f"border-color:{T.ACCENT};}}")
            self.day_btns[d] = b
            grid.addWidget(b, (d - 1) // 7, (d - 1) % 7)
        lay.addWidget(self.dg)

        # live plain-language summary, Google-style ("Occurs every 2 weeks")
        self.summary = label("", T.TEXT_DIM, 10)
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)

        # actions
        row = QHBoxLayout(); row.setSpacing(8)
        save = self._btn("Save", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        save.clicked.connect(self._save)
        clr = self._btn("Clear", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
        clr.clicked.connect(self._clear)
        cancel = self._btn("Cancel", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
        cancel.clicked.connect(self.reject)
        row.addWidget(save); row.addStretch(1); row.addWidget(clr); row.addWidget(cancel)
        lay.addLayout(row)

        self.every.valueChanged.connect(self._sync_ui)
        self.unit.currentIndexChanged.connect(self._sync_ui)
        for b in self.day_btns.values():
            b.clicked.connect(self._sync_ui)
        self._sync_ui()

    def _seg(self, text, active, cb):
        b = QPushButton(text); b.setCheckable(True); b.setChecked(active)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{T.BG_INPUT}; color:{T.TEXT_MUTED};"
            f"border:1px solid {T.BORDER}; border-radius:{T.RADIUS}px; padding:5px 12px;}}"
            f"QPushButton:checked{{background:{T.GREEN_BG}; color:{T.GREEN};"
            f"border-color:{T.GREEN_BORDER};}}")
        b.clicked.connect(cb)
        return b

    def _btn(self, text, fg, bg, border):
        b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{bg}; color:{fg}; border:1px solid {border};"
            f"border-radius:{T.RADIUS}px; padding:6px 16px;}}"
            f"QPushButton:hover{{border-color:{fg};}}"
            f"QPushButton:focus{{border-color:{T.FOCUS};}}"   # was missing — match _button
            f"QPushButton:disabled{{color:{T.TEXT_DIM}; background:transparent;"
            f"border-color:{T.BORDER_SOFT};}}")
        return b

    def _on_days(self):
        return (_UNITS[self.unit.currentIndex()] == "month"
                and self.btn_days.isChecked())

    def _sync_ui(self):
        n = int(self.every.value())
        unit = _UNITS[self.unit.currentIndex()]
        # pluralise the unit list to match N, Google-style ("2 weeks")
        for i, u in enumerate(_UNITS):
            self.unit.setItemText(i, u + ("s" if n != 1 else ""))
        monthly = unit == "month"
        self.btn_days.setVisible(monthly)
        on_days = self._on_days()
        self.dg.setVisible(on_days)
        # the days rule always fires monthly, so "every N" is pinned to 1
        self.every.setEnabled(not on_days)
        if on_days and n != 1:
            self.every.setValue(1); n = 1
        days = sorted(d for d, b in self.day_btns.items() if b.isChecked())
        self.summary.setText(
            _freq_summary(n, unit, days=days if on_days else None)
            if (days or not on_days) else "Pick one or more days below.")
        self.adjustSize()

    def _save(self):
        if self._on_days():
            days = sorted(d for d, b in self.day_btns.items() if b.isChecked())
            self._result = {"type": "days", "days": days} if days else None
        else:
            self._result = {"type": "interval", "every": int(self.every.value()),
                            "unit": _UNITS[self.unit.currentIndex()]}
        self.accept()

    def _clear(self):
        self._result = None
        self.accept()

    @staticmethod
    def edit(parent, repeat):
        dlg = RepeatDialog(parent, repeat)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return (False, None)
        return (True, dlg._result)


class TagDialog(QDialog):
    """Add / create / delete / rename the tags on one item."""

    def __init__(self, parent, tags, suggestions=None):
        super().__init__(parent)
        self.setWindowTitle("Tags")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(300)
        self._tags = [str(t) for t in (tags or [])]
        self._result = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)
        lay.addWidget(label("Tags", T.TEXT, 14, bold=True))

        self._chips_host = QWidget()
        self._chips = QHBoxLayout(self._chips_host)
        self._chips.setContentsMargins(0, 0, 0, 0); self._chips.setSpacing(6)
        lay.addWidget(self._chips_host)

        irow = QHBoxLayout(); irow.setSpacing(6)
        self._inp = QLineEdit(); self._inp.setPlaceholderText("Add a tag…")
        self._inp.setStyleSheet(T.input_style("5px 7px"))
        self._inp.returnPressed.connect(self._add)
        add = self._btn("Add", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        add.clicked.connect(self._add)
        irow.addWidget(self._inp, 1); irow.addWidget(add)
        lay.addLayout(irow)

        sugg = [s for s in (suggestions or []) if s not in self._tags]
        if sugg:
            srow = QHBoxLayout(); srow.setSpacing(6)
            srow.addWidget(label("Existing:", T.TEXT_DIM, 10))
            for s in sugg[:8]:
                b = Clickable(s, T.ACCENT, 10, hover=T.TEXT)
                b.clicked.connect(lambda _=False, t=s: self._add_value(t))
                srow.addWidget(b)
            srow.addStretch(1)
            lay.addLayout(srow)

        arow = QHBoxLayout()
        cancel = self._btn("Cancel", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
        cancel.clicked.connect(self.reject)
        save = self._btn("Save", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addLayout(arow)

        self._rebuild_chips()

    def _btn(self, text, fg, bg, border):
        b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{bg}; color:{fg}; border:1px solid {border};"
            f"border-radius:{T.RADIUS}px; padding:6px 14px;}}"
            f"QPushButton:hover{{border-color:{fg};}}")
        return b

    def _rebuild_chips(self):
        clear_layout(self._chips)
        if not self._tags:
            self._chips.addWidget(label("No tags yet", T.TEXT_DIM, 10))
        for t in self._tags:
            self._chips.addWidget(self._chip(t))
        self._chips.addStretch(1)

    def _chip(self, text):
        w = QWidget()
        w.setStyleSheet(
            f"background:{T.BG_INPUT}; border:1px solid {T.BORDER}; border-radius:8px;")
        h = QHBoxLayout(w); h.setContentsMargins(8, 2, 5, 2); h.setSpacing(4)
        nm = Clickable(text, T.ACCENT, 10, hover=T.TEXT)
        nm.setToolTip("Click to rename")
        nm.clicked.connect(lambda _=False, t=text: self._edit(t))
        x = Clickable("×", T.TEXT_DIM, 12, hover=T.RED)
        x.setToolTip("Remove tag")
        x.clicked.connect(lambda _=False, t=text: self._remove(t))
        h.addWidget(nm); h.addWidget(x)
        return w

    def _add(self):
        self._add_value(self._inp.text())
        self._inp.clear(); self._inp.setFocus()

    def _add_value(self, t):
        t = t.strip()
        if t and t.lower() not in [x.lower() for x in self._tags]:
            self._tags.append(t); self._rebuild_chips()

    def _remove(self, t):
        self._tags = [x for x in self._tags if x != t]
        self._rebuild_chips()

    def _edit(self, t):
        # load into the input so it can be renamed, drop the original
        self._inp.setText(t); self._inp.setFocus(); self._inp.selectAll()
        self._remove(t)

    def _save(self):
        self._result = list(self._tags)
        self.accept()

    @staticmethod
    def edit(parent, tags, suggestions=None):
        dlg = TagDialog(parent, tags, suggestions)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return (False, None)
        return (True, dlg._result)


class CommandPalette(QDialog):
    """Ctrl+K command palette — fuzzy-filter a flat list of actions, Enter runs.

    Every action in here was already reachable by mouse; the palette is purely an
    accelerator, which is what Nielsen heuristic #7 asks for ("shortcuts — hidden
    from novice users — may speed up the interaction for the expert user",
    Henderson p80) and what Henderson p115 lists as the payoff of hotkeys. This
    app's only user is an expert user, so the heuristic most specific to it was
    also the one it scored worst on.

    Actions are ``(label, hint, callable)``. The filter matches the label and hint
    as a subsequence, so "jan" finds "Jump to month: January" and "imp" finds
    "Import bank file…".
    """

    def __init__(self, parent, actions):
        super().__init__(parent)
        self.setWindowTitle("Command palette")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(520)
        self._actions = actions
        self._picked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.SP_L, T.SP_M, T.SP_L, T.SP_M)
        lay.setSpacing(T.SP_S)

        self.box = QLineEdit()
        self.box.setPlaceholderText("Type a command…")
        self.box.setStyleSheet(
            T.input_style("7px 9px") + f"QLineEdit{{font-size:{T.FS_BODY}px;}}")
        self.box.textChanged.connect(self._refresh)
        self.box.returnPressed.connect(self._activate_first)
        lay.addWidget(self.box)

        self.results = QListWidget()
        self.results.setStyleSheet(
            f"QListWidget{{background:transparent; color:{T.TEXT};"
            f"border:none; outline:none;}}"
            f"QListWidget::item{{padding:6px 8px; border-radius:{T.RADIUS}px;}}"
            f"QListWidget::item:selected{{background:{T.BG_HOVER}; color:{T.TEXT};}}")
        self.results.setMinimumHeight(320)
        self.results.itemClicked.connect(self._pick)
        self.results.itemActivated.connect(self._pick)
        lay.addWidget(self.results)

        self._refresh("")
        self.box.setFocus()

    @staticmethod
    def _matches(needle: str, hay: str) -> bool:
        """Subsequence match: every char of `needle` appears in `hay`, in order."""
        it = iter(hay.lower())
        return all(c in it for c in needle.lower())

    def _refresh(self, text=""):
        self.results.clear()
        q = (text or "").strip()
        for label_, hint, _fn in self._actions:
            if q and not (self._matches(q, label_) or self._matches(q, hint)):
                continue
            it = QListWidgetItem(f"{label_}    ·    {hint}" if hint else label_)
            it.setData(Qt.ItemDataRole.UserRole, label_)
            self.results.addItem(it)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _activate_first(self):
        it = self.results.currentItem() or (
            self.results.item(0) if self.results.count() else None)
        if it:
            self._pick(it)

    def _pick(self, item):
        if self._picked:                     # Enter can arrive twice (returnPressed
            return                           # + itemActivated) — run the action once
        key = item.data(Qt.ItemDataRole.UserRole)
        for label_, _hint, fn in self._actions:
            if label_ == key:
                self._picked = True
                self.accept()
                fn()
                return

    def keyPressEvent(self, e):
        # Down/Up move through results while focus stays in the text box, so you
        # never have to Tab out of it to choose.
        if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.results.count():
            row = self.results.currentRow()
            row += 1 if e.key() == Qt.Key.Key_Down else -1
            self.results.setCurrentRow(max(0, min(self.results.count() - 1, row)))
            return
        super().keyPressEvent(e)


class SearchDialog(QDialog):
    """Global search — type to find items, subscriptions, people, accounts,
    transactions; Enter / double-click jumps to the result's page."""

    def __init__(self, parent, search_fn, on_pick):
        super().__init__(parent)
        self.setWindowTitle("Search")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(480)
        self._search_fn = search_fn
        self._on_pick = on_pick
        self._picked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)
        self.box = QLineEdit()
        self.box.setPlaceholderText("Search items, subscriptions, people, accounts…")
        self.box.setStyleSheet(T.input_style("7px 9px") + "QLineEdit{font-size:14px;}")
        self.box.textChanged.connect(self._refresh)
        self.box.returnPressed.connect(self._activate_first)
        lay.addWidget(self.box)

        self.results = QListWidget()
        self.results.setStyleSheet(
            f"QListWidget{{background:{T.BG_INPUT}; color:{T.TEXT};"
            f"border:1px solid {T.BORDER}; outline:none;}}"
            f"QListWidget::item{{padding:6px 8px;}}"
            f"QListWidget::item:selected{{background:{T.BG_HOVER}; color:{T.TEXT};}}")
        self.results.setMinimumHeight(300)
        # A single click opens the result (as well as Enter / double-click) —
        # for a short result list, select-then-open is needless friction.
        self.results.itemClicked.connect(self._pick)
        self.results.itemActivated.connect(self._pick)
        lay.addWidget(self.results)
        self.box.setFocus()

    def _refresh(self, text):
        self.results.clear()
        for r in self._search_fn(text):
            txt = f"[{r['kind']}]  {r['name']}"
            if r.get("detail"):
                txt += f"   ·  {r['detail']}"
            it = QListWidgetItem(txt)
            it.setData(Qt.ItemDataRole.UserRole, r)
            self.results.addItem(it)

    def _activate_first(self):
        if self.results.count():
            self._pick(self.results.item(0))

    def _pick(self, item):
        if self._picked:           # guard: click + activate can both fire
            return
        self._picked = True
        r = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        if r and self._on_pick:
            self._on_pick(r)


class NoteDialog(QDialog):
    """View / edit the free-text note on one item."""

    def __init__(self, parent, name, note):
        super().__init__(parent)
        self.setWindowTitle("Note")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(360)
        self._result = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)
        lay.addWidget(label(f"Note — {name}", T.TEXT, 14, bold=True))
        self.edit = QPlainTextEdit(note or "")
        self.edit.setPlaceholderText("Anything worth remembering about this item…")
        self.edit.setStyleSheet(T.input_style("6px 8px"))
        self.edit.setMinimumHeight(120)
        lay.addWidget(self.edit)
        arow = QHBoxLayout()
        cancel = self._btn("Cancel", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
        cancel.clicked.connect(self.reject)
        save = self._btn("Save", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addLayout(arow)

    def _btn(self, text, fg, bg, border):
        b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{bg}; color:{fg}; border:1px solid {border};"
            f"border-radius:{T.RADIUS}px; padding:6px 14px;}}"
            f"QPushButton:hover{{border-color:{fg};}}")
        return b

    def _save(self):
        self._result = self.edit.toPlainText().strip()
        self.accept()

    @staticmethod
    def edit_note(parent, name, note):
        dlg = NoteDialog(parent, name, note)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return (False, None)
        return (True, dlg._result)


class DateField(QPushButton):
    """A themed button that opens an on-theme calendar popup to pick a date.
    Reuses the same ``_calendar_qss()`` styling as the ledger's due-date picker."""
    picked = pyqtSignal(object)          # datetime.date

    def __init__(self, initial=None):
        super().__init__()
        self._date = initial or date.today()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:{T.BG_INPUT}; color:{T.TEXT};"
            f"border:1px solid {T.BORDER_LIGHT}; border-radius:{T.RADIUS}px;"
            f"padding:6px 10px; text-align:left;}}"
            f"QPushButton:hover{{border-color:{T.GREEN_BORDER};}}")
        self.clicked.connect(self._open)
        self._refresh()

    def date(self):
        return self._date

    def set_date(self, d):
        if d:
            self._date = d
            self._refresh()

    def _refresh(self):
        self.setText("📅  " + self._date.strftime("%a %d %b %Y") + "      ▾")

    def _open(self):
        m = QMenu(self)
        m.setStyleSheet(
            f"QMenu{{background:{T.BG_CARD}; border:1px solid {T.BORDER_LIGHT};"
            f"padding:6px;}}")
        cal = QCalendarWidget()
        cal.setFixedSize(266, 220)
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setStyleSheet(_calendar_qss())
        cal.setCurrentPage(self._date.year, self._date.month)
        cal.setSelectedDate(QDate(self._date.year, self._date.month, self._date.day))
        cal.clicked.connect(lambda qd: self._pick(qd, m))
        wa = QWidgetAction(m); wa.setDefaultWidget(cal); m.addAction(wa)
        m.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _pick(self, qd, menu):
        menu.close()
        self._date = date(qd.year(), qd.month(), qd.day())
        self._refresh()
        self.picked.emit(self._date)


class PersonDialog(QDialog):
    """Create / edit a payee record — the personal details stored as JSON on
    the person entry in the store ({id, name, email, phone, note})."""

    def __init__(self, parent, person=None):
        super().__init__(parent)
        self._editing = person is not None
        self.setWindowTitle("Edit person" if self._editing else "Add person")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(340)
        self._result = None
        p = person or {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(9)
        lay.addWidget(label("Edit person" if self._editing else "Add person",
                            T.TEXT, 15, bold=True))

        ist = T.input_style("6px 8px")
        self.name = QLineEdit(p.get("name", ""))
        self.name.setPlaceholderText("Name (required)")
        self.email = QLineEdit(p.get("email", ""))
        self.email.setPlaceholderText("e.g. sam@example.com")
        self.phone = QLineEdit(p.get("phone", ""))
        self.phone.setPlaceholderText("e.g. 0400 000 000")
        self.note = QLineEdit(p.get("note", ""))
        self.note.setPlaceholderText("e.g. housemate, pays via beem")
        for cap, w in (("Name", self.name), ("Email", self.email),
                       ("Phone", self.phone), ("Note", self.note)):
            w.setStyleSheet(ist)
            lay.addWidget(label(cap, T.TEXT_MUTED, 10)); lay.addWidget(w)

        arow = QHBoxLayout()
        cancel = QPushButton("Cancel"); save = QPushButton(
            "Save changes" if self._editing else "Add person")
        for b, fg, bg, border in ((cancel, T.TEXT_MUTED, T.BG_INPUT, T.BORDER),
                                  (save, T.GREEN, T.GREEN_BG, T.GREEN_BORDER)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{bg}; color:{fg}; border:1px solid "
                f"{border}; border-radius:{T.RADIUS}px; padding:6px 14px;}}"
                f"QPushButton:hover{{border-color:{fg};}}")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addSpacing(4); lay.addLayout(arow)
        self.name.setFocus()

    def _save(self):
        nm = self.name.text().strip()
        if not nm:
            self.name.setFocus(); return
        self._result = {"name": nm,
                        "email": self.email.text().strip(),
                        "phone": self.phone.text().strip(),
                        "note": self.note.text().strip()}
        self.accept()

    @staticmethod
    def create(parent):
        dlg = PersonDialog(parent)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg._result

    @staticmethod
    def edit(parent, person):
        dlg = PersonDialog(parent, person)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg._result


class AccountDialog(QDialog):
    """Create / edit a net-worth account: {name, kind, balance}. Same
    static create()/edit() shape as PersonDialog."""
    _KINDS = [("Cash", "cash"), ("Savings", "savings"),
              ("Investment", "investment"), ("Debt / loan", "debt"),
              ("Credit card", "credit")]

    def __init__(self, parent, currency="$", account=None):
        super().__init__(parent)
        self._editing = account is not None
        self.setWindowTitle("Edit account" if self._editing else "Add account")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(340)
        self._result = None
        a = account or {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(9)
        lay.addWidget(label("Edit account" if self._editing else "Add account",
                            T.TEXT, 15, bold=True))
        ist = T.input_style("6px 8px")

        self.name = QLineEdit(a.get("name", ""))
        self.name.setPlaceholderText("e.g. ANZ Plus, Shares, Home loan")
        self.name.setStyleSheet(ist)
        lay.addWidget(label("Name", T.TEXT_MUTED, 10)); lay.addWidget(self.name)

        self.kind = QComboBox(); self.kind.addItems([k[0] for k in self._KINDS])
        idx = next((i for i, (_, v) in enumerate(self._KINDS)
                    if v == a.get("kind", "cash")), 0)
        self.kind.setCurrentIndex(idx)
        lay.addWidget(label("Type", T.TEXT_MUTED, 10)); lay.addWidget(self.kind)

        lay.addWidget(label("Balance", T.TEXT_MUTED, 10))
        self.balance = MoneySpin(); self.balance.setRange(0, 100_000_000)
        self.balance.setDecimals(2); self.balance.setPrefix(currency)
        self.balance.setValue(float(a.get("balance", 0.0)))
        self.balance.setStyleSheet(ist)
        lay.addWidget(self.balance)
        hint = label("Debt and credit accounts count as liabilities — subtracted "
                     "from net worth. Enter the balance as a positive number.",
                     T.TEXT_DIM, 10)
        hint.setWordWrap(True); lay.addWidget(hint)

        arow = QHBoxLayout()
        cancel = QPushButton("Cancel"); save = QPushButton(
            "Save changes" if self._editing else "Add account")
        for b, fg, bg, border in ((cancel, T.TEXT_MUTED, T.BG_INPUT, T.BORDER),
                                  (save, T.GREEN, T.GREEN_BG, T.GREEN_BORDER)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{bg}; color:{fg}; border:1px solid "
                f"{border}; border-radius:{T.RADIUS}px; padding:6px 14px;}}"
                f"QPushButton:hover{{border-color:{fg};}}")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addSpacing(4); lay.addLayout(arow)
        self.name.setFocus()

    def _save(self):
        nm = self.name.text().strip()
        if not nm:
            self.name.setFocus(); return
        self._result = {"name": nm,
                        "kind": self._KINDS[self.kind.currentIndex()][1],
                        "balance": float(self.balance.value())}
        self.accept()

    @staticmethod
    def create(parent, currency="$"):
        dlg = AccountDialog(parent, currency)
        place_near_cursor(dlg)
        return dlg._result if dlg.exec() == QDialog.DialogCode.Accepted else None

    @staticmethod
    def edit(parent, account, currency="$"):
        dlg = AccountDialog(parent, currency, account=account)
        place_near_cursor(dlg)
        return dlg._result if dlg.exec() == QDialog.DialogCode.Accepted else None


class TrackerItemDialog(QDialog):
    """Create / edit a cost-per-use tracked item (skincare, vitamins, anything
    bought once and used repeatedly). Same static create()/edit() shape as
    AccountDialog."""

    def __init__(self, parent, currency="$", item=None):
        super().__init__(parent)
        self._editing = item is not None
        self.setWindowTitle("Edit tracked item" if self._editing else "Add tracked item")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(360)
        self._result = None
        a = item or {}
        ist = T.input_style("6px 8px")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(9)
        lay.addWidget(label("Edit tracked item" if self._editing else "Add tracked item",
                            T.TEXT, 15, bold=True))

        self.name = QLineEdit(a.get("name", ""))
        self.name.setPlaceholderText("e.g. Vitamin C serum, Multivitamin")
        self.name.setStyleSheet(ist)
        lay.addWidget(label("Name", T.TEXT_MUTED, 10)); lay.addWidget(self.name)

        row1 = QHBoxLayout(); row1.setSpacing(10)
        qcol = QVBoxLayout()
        qcol.addWidget(label("Quantity in item", T.TEXT_MUTED, 10))
        self.quantity = QDoubleSpinBox(); self.quantity.setRange(0.01, 1_000_000)
        self.quantity.setDecimals(2); self.quantity.setValue(float(a.get("quantity", 30.0)))
        self.quantity.setStyleSheet(ist)
        qcol.addWidget(self.quantity)
        row1.addLayout(qcol)

        ucol = QVBoxLayout()
        ucol.addWidget(label("Unit (optional)", T.TEXT_MUTED, 10))
        self.unit = QLineEdit(a.get("unit", ""))
        self.unit.setPlaceholderText("capsules, mL…")
        self.unit.setStyleSheet(ist)
        ucol.addWidget(self.unit)
        row1.addLayout(ucol)
        lay.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(10)
        pcol = QVBoxLayout()
        pcol.addWidget(label("Amount per use", T.TEXT_MUTED, 10))
        self.per_use = QDoubleSpinBox(); self.per_use.setRange(0.01, 1_000_000)
        self.per_use.setDecimals(2); self.per_use.setValue(float(a.get("per_use_amount", 1.0)))
        self.per_use.setStyleSheet(ist)
        pcol.addWidget(self.per_use)
        row2.addLayout(pcol)

        dcol = QVBoxLayout()
        dcol.addWidget(label("Uses per day", T.TEXT_MUTED, 10))
        self.uses_day = QDoubleSpinBox(); self.uses_day.setRange(0.0, 50.0)
        self.uses_day.setDecimals(2); self.uses_day.setValue(float(a.get("uses_per_day", 1.0)))
        self.uses_day.setStyleSheet(ist)
        dcol.addWidget(self.uses_day)
        row2.addLayout(dcol)
        lay.addLayout(row2)

        lay.addWidget(label("Item cost (total price paid)", T.TEXT_MUTED, 10))
        self.cost = MoneySpin(); self.cost.setRange(0, 1_000_000)
        self.cost.setDecimals(2); self.cost.setPrefix(currency)
        self.cost.setValue(float(a.get("item_cost", 0.0)))
        self.cost.setStyleSheet(ist)
        lay.addWidget(self.cost)

        hint = label("Cost per use = item cost ÷ (quantity ÷ amount per use). "
                     "Cost per day = cost per use × uses per day.",
                     T.TEXT_DIM, 10)
        hint.setWordWrap(True); lay.addWidget(hint)

        arow = QHBoxLayout()
        cancel = QPushButton("Cancel"); save = QPushButton(
            "Save changes" if self._editing else "Add item")
        for b, fg, bg, border in ((cancel, T.TEXT_MUTED, T.BG_INPUT, T.BORDER),
                                  (save, T.GREEN, T.GREEN_BG, T.GREEN_BORDER)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{bg}; color:{fg}; border:1px solid "
                f"{border}; border-radius:{T.RADIUS}px; padding:6px 14px;}}"
                f"QPushButton:hover{{border-color:{fg};}}")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addSpacing(4); lay.addLayout(arow)
        self.name.setFocus()

    def _save(self):
        nm = self.name.text().strip()
        if not nm:
            self.name.setFocus(); return
        self._result = {
            "name": nm,
            "quantity": float(self.quantity.value()),
            "unit": self.unit.text().strip(),
            "per_use_amount": float(self.per_use.value()),
            "uses_per_day": float(self.uses_day.value()),
            "item_cost": float(self.cost.value()),
        }
        self.accept()

    @staticmethod
    def create(parent, currency="$"):
        dlg = TrackerItemDialog(parent, currency)
        place_near_cursor(dlg)
        return dlg._result if dlg.exec() == QDialog.DialogCode.Accepted else None

    @staticmethod
    def edit(parent, item, currency="$"):
        dlg = TrackerItemDialog(parent, currency, item=item)
        place_near_cursor(dlg)
        return dlg._result if dlg.exec() == QDialog.DialogCode.Accepted else None


class BudgetDialog(QDialog):
    """Set the monthly ideal (budget) for each expense category. Returns
    {category_id: ideal} on save."""

    def __init__(self, parent, rows, currency="$"):
        super().__init__(parent)
        self.setWindowTitle("Set category budgets")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(430)
        self._result = None
        self._spins = {}                 # category id → spinbox

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(8)
        lay.addWidget(label("Set category budgets", T.TEXT, 15, bold=True))
        lay.addWidget(label("The monthly amount each category should stay under. "
                            "Leave 0 to leave a category unbudgeted.", T.TEXT_MUTED, 11))
        ist = T.input_style("4px 6px")

        box = QVBoxLayout(); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(3)
        inner = QWidget(); inner.setLayout(box)
        inner.setStyleSheet("background:transparent;")
        sc = BoundedScroll(); sc.setWidget(inner); sc.setWidgetResizable(True)
        sc.setFixedHeight(300)
        sc.setStyleSheet(f"QScrollArea{{background:{T.BG_INPUT};"
                         f"border:1px solid {T.BORDER_LIGHT};}}")
        if not rows:
            box.addWidget(label("No expense categories yet — add expenses on the "
                                "Overview first.", T.TEXT_DIM, 11))
        for r in rows:
            rw = QHBoxLayout(); rw.setContentsMargins(6, 1, 6, 1); rw.setSpacing(8)
            rw.addWidget(label(r.get("name", ""), T.TEXT, 12)); rw.addStretch(1)
            if r.get("planned"):
                rw.addWidget(label(f"planned {money(r['planned'], currency, signed=False)}",
                                   T.TEXT_DIM, 10))
            spin = MoneySpin(); spin.setRange(0, 10_000_000); spin.setDecimals(2)
            spin.setPrefix(currency); spin.setValue(float(r.get("ideal", 0.0)))
            spin.setFixedWidth(112); spin.setStyleSheet(ist)
            self._spins[r["id"]] = spin
            rw.addWidget(spin)
            box.addLayout(rw)
        box.addStretch(1)
        lay.addWidget(sc)

        arow = QHBoxLayout()
        cancel = QPushButton("Cancel"); save = QPushButton("Save budgets")
        for b, fg, bg, border in ((cancel, T.TEXT_MUTED, T.BG_INPUT, T.BORDER),
                                  (save, T.GREEN, T.GREEN_BG, T.GREEN_BORDER)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{bg}; color:{fg}; border:1px solid "
                f"{border}; border-radius:{T.RADIUS}px; padding:6px 14px;}}"
                f"QPushButton:hover{{border-color:{fg};}}")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addSpacing(4); lay.addLayout(arow)

    def _save(self):
        self._result = {cid: float(sp.value()) for cid, sp in self._spins.items()}
        self.accept()

    @staticmethod
    def edit(parent, rows, currency="$"):
        dlg = BudgetDialog(parent, rows, currency)
        place_near_cursor(dlg)
        return dlg._result if dlg.exec() == QDialog.DialogCode.Accepted else None


class TransactionReviewDialog(QDialog):
    """Review imported bank transactions and assign/correct a category per
    row. Previously the only UI, none — ItemStore.set_transaction_category
    had no consumer at all, so a transaction that didn't happen to match a
    rule or an exact expense name had no way to ever be categorised, and
    there was no way to see which raw descriptions were uncategorised in
    the first place. Sorted uncategorised-first so the highest-value rows
    are the first ones seen. Returns {txn_id: new_category} on save."""

    def __init__(self, parent, transactions, expense_names, currency="$"):
        super().__init__(parent)
        self.setWindowTitle("Review transactions")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumSize(620, 480)
        self._currency = currency
        self._expense_names = expense_names
        self._edits = {}          # txn id -> QLineEdit
        self._result = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(9)
        lay.addWidget(label("Review transactions", T.TEXT, 15, bold=True))
        lay.addWidget(label(
            "Uncategorised transactions first. Type a category for each — an "
            "existing expense name (autocompleted) reconciles against the "
            "plan; anything else still tracks the spend, just without a "
            "budget comparison.", T.TEXT_DIM, 10))

        hdr = QHBoxLayout(); hdr.setContentsMargins(4, 0, 4, 0); hdr.setSpacing(8)
        for cap, w in (("Date", 80), ("Description", 220), ("Amount", 70)):
            l = label(cap, T.TEXT_DIM, 10, bold=True); l.setFixedWidth(w)
            hdr.addWidget(l)
        hdr.addWidget(label("Category", T.TEXT_DIM, 10, bold=True))
        lay.addLayout(hdr)

        box = QVBoxLayout(); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(3)
        inner = QWidget(); inner.setLayout(box)
        inner.setStyleSheet("background:transparent;")
        sc = BoundedScroll(); sc.setWidget(inner); sc.setWidgetResizable(True)
        sc.setStyleSheet(f"QScrollArea{{background:{T.BG_INPUT};"
                         f"border:1px solid {T.BORDER_LIGHT};}}")
        lay.addWidget(sc, 1)

        txns = sorted(transactions,
                      key=lambda t: (bool(t.get("category")), t.get("date", "")),
                      reverse=False)
        if not txns:
            box.addWidget(label("No transactions imported yet.", T.TEXT_DIM, 11))
        for t in txns:
            box.addWidget(self._txn_row(t))
        box.addStretch(1)

        arow = QHBoxLayout()
        close = QPushButton("Close"); save = QPushButton("Save changes")
        for b, fg, bg, border in ((close, T.TEXT_MUTED, T.BG_INPUT, T.BORDER),
                                  (save, T.GREEN, T.GREEN_BG, T.GREEN_BORDER)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{bg}; color:{fg}; border:1px solid "
                f"{border}; border-radius:{T.RADIUS}px; padding:6px 14px;}}"
                f"QPushButton:hover{{border-color:{fg};}}")
        close.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(close); arow.addWidget(save)
        lay.addSpacing(4); lay.addLayout(arow)

    def _txn_row(self, t):
        row = QWidget()
        h = QHBoxLayout(row); h.setContentsMargins(4, 2, 4, 2); h.setSpacing(8)
        d = label(t.get("date", ""), T.TEXT_DIM, 10); d.setFixedWidth(80)
        h.addWidget(d)
        desc = label(t.get("description", ""), T.TEXT, 11); desc.setFixedWidth(220)
        h.addWidget(desc)
        amt_val = float(t.get("amount", 0))
        amt = label(money(amt_val, self._currency), T.GREEN if amt_val >= 0 else T.RED, 11)
        amt.setFixedWidth(70)
        h.addWidget(amt)
        edit = QLineEdit(t.get("category", ""))
        edit.setPlaceholderText("category…")
        edit.setStyleSheet(
            f"background:{T.BG_APP}; color:{T.TEXT}; border:1px solid {T.BORDER};"
            f"padding:3px 6px;")
        completer = QCompleter(self._expense_names, edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        edit.setCompleter(completer)
        h.addWidget(edit, 1)
        self._edits[t["id"]] = edit
        return row

    def _save(self):
        self._result = {tid: edit.text().strip() for tid, edit in self._edits.items()}
        self.accept()

    @staticmethod
    def review(parent, transactions, expense_names, currency="$"):
        dlg = TransactionReviewDialog(parent, transactions, expense_names, currency)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg._result


class SharedPlanDialog(QDialog):
    """Add a subscription: solo (just me), a cost split with others, or income
    others pay me — with a billing cycle and a member list."""

    # Ordered by ascending period so the dropdown reads shortest → longest.
    # Anything else (e.g. every 6 months) lives under "Custom…".
    _CYCLES = [("Weekly",         {"type": "interval", "every": 1, "unit": "week"}),
               ("Monthly",        {"type": "interval", "every": 1, "unit": "month"}),
               ("Quarterly",      {"type": "interval", "every": 3, "unit": "month"}),
               ("Yearly",         {"type": "interval", "every": 1, "unit": "year"})]

    # the extra billing-cycle entry that switches to specific days of the month
    _DAYS_LABEL = "Specific days of month…"
    # Google-style escape hatch: "Repeat every [N] [unit]"
    _CUSTOM_LABEL = "Custom…"

    def __init__(self, parent, currency="$", existing=None, store=None):
        super().__init__(parent)
        self._editing = existing is not None
        self._store = store
        self._currency = currency
        self._mem_rows = []          # [{name, cb, spin, row}] — one per person
        self.setWindowTitle("Edit subscription" if self._editing else "Add subscription")
        self.setStyleSheet(f"QDialog{{background:{T.BG_CARD};}}")
        self.setMinimumWidth(400)
        self._result = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(10)
        lay.addWidget(label("Edit subscription" if self._editing else "Add subscription",
                            T.TEXT, 15, bold=True))

        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Netflix, Spotify Family, Acme retainer")
        self.name.setStyleSheet(self._ist())
        lay.addWidget(label("Name", T.TEXT_MUTED, 10)); lay.addWidget(self.name)

        row = QHBoxLayout(); row.setSpacing(10)
        cbox = QVBoxLayout(); cbox.addWidget(label("Amount", T.TEXT_MUTED, 10))
        self.amount = MoneySpin(); self.amount.setRange(0, 1_000_000)
        self.amount.setDecimals(2); self.amount.setPrefix(currency); self.amount.setFixedWidth(130)
        cbox.addWidget(self.amount); row.addLayout(cbox)
        cyb = QVBoxLayout(); cyb.addWidget(label("Billing cycle", T.TEXT_MUTED, 10))
        self.cycle = QComboBox()
        self.cycle.addItems([c[0] for c in self._CYCLES]
                            + [self._DAYS_LABEL, self._CUSTOM_LABEL])
        self.cycle.setCurrentText("Monthly")     # sensible default for a new sub
        self.cycle.currentIndexChanged.connect(self._sync)
        cyb.addWidget(self.cycle); row.addLayout(cyb)
        row.addStretch(1); lay.addLayout(row)

        # custom cadence — Google Calendar's "Repeat every [N] [unit]" row
        self._custom_host = QWidget()
        crow = QHBoxLayout(self._custom_host)
        crow.setContentsMargins(0, 0, 0, 0); crow.setSpacing(8)
        crow.addWidget(label("Repeat every", T.TEXT, 12))
        self.custom_every = QSpinBox(); self.custom_every.setRange(1, 99)
        self.custom_every.setFixedWidth(70)
        crow.addWidget(self.custom_every)
        self.custom_unit = QComboBox(); self.custom_unit.addItems(_UNITS)
        self.custom_unit.setCurrentText("month")
        crow.addWidget(self.custom_unit); crow.addStretch(1)
        lay.addWidget(self._custom_host)
        self.custom_every.valueChanged.connect(self._sync)
        self.custom_unit.currentIndexChanged.connect(self._sync)

        # weekday chips for weekly cadences — picking one moves the anchor
        # date to the next such weekday (the rule stays anchor-relative)
        self._wd_host = QWidget()
        wrow = QHBoxLayout(self._wd_host)
        wrow.setContentsMargins(0, 0, 0, 0); wrow.setSpacing(8)
        wrow.addWidget(label("On", T.TEXT_MUTED, 10))
        self.weekdays = WeekdayChips()
        wrow.addWidget(self.weekdays); wrow.addStretch(1)
        lay.addWidget(self._wd_host)
        self.weekdays.changed.connect(self._on_weekday)

        # first billing / anchor date — determines *which* day (and month, for
        # yearly) the cycle lands on.  Opens an on-theme calendar popup.
        self._date_lbl = label("First billing date", T.TEXT_MUTED, 10)
        self.date_field = DateField(date.today())
        self.date_field.picked.connect(lambda _=None: self._sync())
        drow = QHBoxLayout(); drow.setSpacing(10)
        dcol = QVBoxLayout(); dcol.addWidget(self._date_lbl)
        dcol.addWidget(self.date_field); drow.addLayout(dcol); drow.addStretch(1)
        lay.addLayout(drow)
        self._date_hint = label("", T.TEXT_DIM, 10); self._date_hint.setWordWrap(True)
        lay.addWidget(self._date_hint)

        # specific days-of-month grid (shown only for the "Specific days" cycle)
        self._days_lbl = label("Repeats monthly on these days", T.TEXT_MUTED, 10)
        self.days_grid = QWidget()
        dgrid = QGridLayout(self.days_grid)
        dgrid.setContentsMargins(0, 0, 0, 0); dgrid.setSpacing(3)
        self.day_btns = {}
        for dnum in range(1, 32):
            b = QPushButton(str(dnum)); b.setCheckable(True)
            b.setFixedSize(30, 24); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{T.BG_INPUT}; color:{T.TEXT_MUTED};"
                f"border:1px solid {T.BORDER}; border-radius:{T.RADIUS}px; font-size:11px;}}"
                f"QPushButton:checked{{background:{T.ACCENT}; color:{T.ON_ACCENT};"
                f"border-color:{T.ACCENT};}}")
            b.clicked.connect(self._sync)
            self.day_btns[dnum] = b
            dgrid.addWidget(b, (dnum - 1) // 7, (dnum - 1) % 7)
        lay.addWidget(self._days_lbl); lay.addWidget(self.days_grid)

        lay.addWidget(label("Type", T.TEXT_MUTED, 10))
        self.kind = QComboBox(); self.kind.addItems(
            ["Just me (solo)", "I pay & split with others", "Others pay me"])
        self.kind.currentIndexChanged.connect(self._sync)
        lay.addWidget(self.kind)

        srow = QHBoxLayout(); srow.setSpacing(10)
        self._split_lbl = label("Split", T.TEXT_MUTED, 10)
        self.split = QComboBox(); self.split.addItems(["Even split", "Custom amounts"])
        self.split.currentIndexChanged.connect(self._sync)
        self.owner = QCheckBox("I pay a share too")
        self.owner.setToolTip(
            "Checked: the cost is split between you and the members.\n"
            "Unchecked: the members cover the whole cost between them\n"
            "and simply reimburse you.")
        self.owner.setStyleSheet(f"color:{T.TEXT_MUTED};")
        self.owner.toggled.connect(lambda _=False: self._sync())
        srow.addWidget(self._split_lbl); srow.addWidget(self.split)
        srow.addWidget(self.owner); srow.addStretch(1)
        self._srow_host = QWidget(); self._srow_host.setLayout(srow)
        lay.addWidget(self._srow_host)

        self._mem_lbl = label("Members — tick who's on this plan", T.TEXT_MUTED, 10)
        lay.addWidget(self._mem_lbl)
        # Checkbox list of people (replaces the old free-text "one per line").
        self._mem_box = QVBoxLayout()
        self._mem_box.setContentsMargins(0, 0, 0, 0); self._mem_box.setSpacing(2)
        mem_inner = QWidget(); mem_inner.setLayout(self._mem_box)
        mem_inner.setStyleSheet("background:transparent;")
        self._mem_scroll = BoundedScroll(); self._mem_scroll.setWidget(mem_inner)
        self._mem_scroll.setWidgetResizable(True)
        self._mem_scroll.setFixedHeight(112)
        self._mem_scroll.setStyleSheet(
            f"QScrollArea{{background:{T.BG_INPUT}; border:1px solid {T.BORDER_LIGHT};}}")
        lay.addWidget(self._mem_scroll)
        self._empty_mem_lbl = label(
            "No people yet — add someone with “+ New person”.", T.TEXT_DIM, 10)
        self._empty_mem_lbl.setWordWrap(True)
        lay.addWidget(self._empty_mem_lbl)
        self._new_person_btn = Clickable("+ New person", T.ACCENT, 11,
                                         hover=T.GREEN_BRIGHT)
        self._new_person_btn.clicked.connect(self._add_new_person)
        lay.addWidget(self._new_person_btn)
        for _p in (self._store.people() if self._store else []):
            self._add_member_row(_p.get("name", ""))
        self.hint = label("", T.TEXT_DIM, 10); self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        arow = QHBoxLayout()
        cancel = self._btn("Cancel", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
        cancel.clicked.connect(self.reject)
        save = self._btn("Save changes" if self._editing else "Add",
                         T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        save.clicked.connect(self._save)
        arow.addStretch(1); arow.addWidget(cancel); arow.addWidget(save)
        lay.addLayout(arow)
        if existing:
            self._prefill(existing)
        self._sync()

    def _ist(self):
        return T.input_style("5px 7px")

    def _btn(self, text, fg, bg, border):
        b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{bg}; color:{fg}; border:1px solid {border};"
            f"border-radius:{T.RADIUS}px; padding:6px 14px;}}"
            f"QPushButton:hover{{border-color:{fg};}}")
        return b

    # -- member checkbox list -------------------------------------------- #
    def _add_member_row(self, name, checked=False, share=0.0):
        """One tickable person row: [✓ name] … [share spinbox (custom only)]."""
        rw = QWidget(); h = QHBoxLayout(rw)
        h.setContentsMargins(6, 1, 6, 1); h.setSpacing(8)
        cb = QCheckBox(name); cb.setChecked(checked)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setStyleSheet(f"color:{T.TEXT};")
        cb.toggled.connect(self._sync)
        spin = MoneySpin(); spin.setRange(0, 1_000_000); spin.setDecimals(2)
        spin.setPrefix(self._currency); spin.setValue(float(share))
        spin.setFixedWidth(104); spin.setStyleSheet(self._ist())
        spin.valueChanged.connect(self._sync)
        h.addWidget(cb); h.addStretch(1); h.addWidget(spin)
        self._mem_box.addWidget(rw)
        row = {"name": name, "cb": cb, "spin": spin, "row": rw}
        self._mem_rows.append(row)
        return row

    def _add_new_person(self):
        res = PersonDialog.create(self)
        if not res:
            return
        nm = res["name"]
        if self._store:
            self._store.add_person(nm, email=res.get("email", ""),
                                   phone=res.get("phone", ""), note=res.get("note", ""))
        existing = next((r for r in self._mem_rows
                         if r["name"].lower() == nm.lower()), None)
        if existing:
            existing["cb"].setChecked(True)
        else:
            self._add_member_row(nm, checked=True)
        self._sync()

    def _checked_members(self):
        return [r for r in self._mem_rows if r["cb"].isChecked()]

    def _kind(self):
        return ["solo", "split", "income"][self.kind.currentIndex()]

    def _is_custom(self):
        return self.split.currentIndex() == 1

    def _on_days(self):
        return self.cycle.currentIndex() == len(self._CYCLES)

    def _on_custom(self):
        return self.cycle.currentIndex() == len(self._CYCLES) + 1

    def _every_unit(self):
        """(every, unit) for the currently selected non-days cadence."""
        if self._on_custom():
            return (int(self.custom_every.value()),
                    _UNITS[self.custom_unit.currentIndex()])
        c = self._CYCLES[self.cycle.currentIndex()][1]
        return int(c["every"]), c["unit"]

    def _on_weekday(self, wd):
        """Chip picked → shift the anchor to the next such weekday."""
        d = self.date_field.date()
        self.date_field.set_date(d + timedelta(days=(wd - d.weekday()) % 7))
        self._sync()

    def _sync(self):
        on_days = self._on_days()
        on_custom = self._on_custom()
        self._days_lbl.setVisible(on_days)
        self.days_grid.setVisible(on_days)
        self._custom_host.setVisible(on_custom)
        if on_custom:
            # pluralise units to match N, Google-style ("2 weeks")
            n = int(self.custom_every.value())
            for i, u in enumerate(_UNITS):
                self.custom_unit.setItemText(i, u + ("s" if n != 1 else ""))
        # date field is meaningless for "specific days of month" (that rule
        # carries its own days); hide it there, otherwise explain the anchor.
        self._date_lbl.setVisible(not on_days)
        self.date_field.setVisible(not on_days)
        anchor = self.date_field.date()
        if on_days:
            days = sorted(d for d, b in self.day_btns.items() if b.isChecked())
            self._wd_host.setVisible(False)
            self._date_hint.setText(_freq_summary(1, "month", days=days) if days
                                    else "Pick one or more billing days.")
        else:
            every, unit = self._every_unit()
            # weekday chips only make sense for a weekly cadence
            self._wd_host.setVisible(unit == "week")
            if unit == "week":
                self.weekdays.set_weekday(anchor.weekday())
            self._date_hint.setText(
                _freq_summary(every, unit, anchor=anchor)
                + f" · starts {anchor.strftime('%d %b %Y')}")
        solo = self._kind() == "solo"
        for w in (self._srow_host, self._mem_lbl, self._mem_scroll,
                  self._new_person_btn):
            w.setVisible(not solo)
        self._empty_mem_lbl.setVisible(not solo and not self._mem_rows)
        if solo:
            self.hint.setText("A subscription only you pay.")
            return
        custom = self._is_custom()
        self.owner.setVisible(self._kind() == "split" and not custom)
        for r in self._mem_rows:                 # per-person share only for custom
            r["spin"].setVisible(custom)
        n = len(self._checked_members())
        if custom:
            self.hint.setText("Custom: tick each member and set their exact share.")
        elif self._kind() == "split":
            if self.owner.isChecked():
                ways = f"{n + 1} ways (members + you)" if n else "members + you"
                self.hint.setText(f"Even: cost splits {ways} — you pay one share too.")
            else:
                self.hint.setText("Even: members cover the whole cost between them — "
                                  "they reimburse you in full.")
        else:
            self.hint.setText("Even: the amount is divided equally between the "
                              "ticked members.")

    def _recurrence(self):
        if self._on_days():
            days = sorted(d for d, b in self.day_btns.items() if b.isChecked())
            if not days:
                return None
            return {"type": "days", "days": days}
        if self._on_custom():
            return {"type": "interval", "every": int(self.custom_every.value()),
                    "unit": _UNITS[self.custom_unit.currentIndex()]}
        return self._CYCLES[self.cycle.currentIndex()][1]

    def _prefill(self, d):
        self.name.setText(d.get("name", ""))
        self.amount.setValue(float(d.get("amount", 0.0)))
        start = d.get("start")
        if start:
            try:
                self.date_field.set_date(date.fromisoformat(start))
            except ValueError:
                pass
        rec = d.get("recurrence") or {}
        if rec.get("type") == "days":
            self.cycle.setCurrentIndex(len(self._CYCLES))
            for x in rec.get("days", []):
                if x in self.day_btns:
                    self.day_btns[x].setChecked(True)
        elif not rec:
            self.cycle.setCurrentText("Monthly")
        else:
            idx = next((i for i, (_, c) in enumerate(self._CYCLES)
                        if c.get("every") == rec.get("every")
                        and c.get("unit") == rec.get("unit")), None)
            if idx is None:              # non-preset cadence → Custom…
                self.cycle.setCurrentIndex(len(self._CYCLES) + 1)
                self.custom_every.setValue(int(rec.get("every", 1)))
                unit = rec.get("unit", "month")
                if unit in _UNITS:
                    self.custom_unit.setCurrentIndex(_UNITS.index(unit))
            else:
                self.cycle.setCurrentIndex(idx)
        shared = d.get("shared")
        if not shared:
            self.kind.setCurrentIndex(0)
            return
        self.kind.setCurrentIndex(1 if d.get("type") == "expense" else 2)
        custom = shared.get("split") == "custom"
        self.split.setCurrentIndex(1 if custom else 0)
        self.owner.setChecked(bool(shared.get("owner_pays")))
        for m in shared.get("members", []):
            nm = m.get("name", "")
            r = next((r for r in self._mem_rows
                      if r["name"].lower() == nm.lower()), None)
            if r is None:                        # a member not in the registry
                r = self._add_member_row(nm)     # → still show it, ticked
            r["cb"].setChecked(True)
            r["spin"].setValue(float(m.get("share", 0.0)))

    def _invalid(self, w, msg):
        """Focus the offending field and explain what's missing."""
        from PyQt6.QtWidgets import QToolTip
        w.setFocus()
        QToolTip.showText(w.mapToGlobal(w.rect().bottomLeft()), msg, w)

    def _save(self):
        name = self.name.text().strip()
        if not name:
            self._invalid(self.name, "Enter a name."); return
        rec = self._recurrence()
        if rec is None and self._on_days():
            self._invalid(self.days_grid,
                          "Pick at least one billing day."); return
        kind = self._kind()
        start_iso = self.date_field.date().isoformat()
        if kind == "solo":
            self._result = {"name": name, "amount": float(self.amount.value()),
                            "solo": True, "type": "expense", "recurrence": rec,
                            "start": start_iso}
            self.accept(); return
        custom = self._is_custom()
        members = []
        for r in self._checked_members():
            m = {"name": r["name"]}
            if custom:
                m["share"] = float(r["spin"].value())
            members.append(m)
        if not members:
            self._invalid(self._mem_scroll,
                          "Tick at least one member (or add one with "
                          "“+ New person”)."); return
        self._result = {
            "name": name, "amount": float(self.amount.value()),
            "type": "expense" if kind == "split" else "income",
            "recurrence": rec, "solo": False, "start": start_iso,
            "shared": {
                "split": "custom" if custom else "even",
                "owner_pays": (bool(self.owner.isChecked()) and not custom
                               and kind == "split"),
                "members": members,
            },
        }
        self.accept()

    @staticmethod
    def create(parent, currency="$", store=None):
        dlg = SharedPlanDialog(parent, currency, store=store)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg._result

    @staticmethod
    def edit(parent, defn, currency="$", store=None):
        dlg = SharedPlanDialog(parent, currency, existing=defn, store=store)
        place_near_cursor(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg._result


# --------------------------------------------------------------------------- #
#  Summary card (right-hand top)
# --------------------------------------------------------------------------- #
class StatBox(QFrame):
    def __init__(self, title, amount, fg):
        super().__init__()
        # No tinted fill: the coloured number is the mark; a green fill behind a
        # green number behind a "+" is three greens saying one thing (critique
        # §3.1). Space separates the two boxes, not a surface.
        self.setStyleSheet("QFrame{background:transparent; border:none;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(2)
        lay.addWidget(label(title, fg, 11, bold=True))
        self.amt = label(amount, fg, 16, bold=True)
        lay.addWidget(self.amt)

    def set_amount(self, text):
        self.amt.setText(text)


def retain_size(widget):
    """Keep a hidden widget's layout space reserved so toggling its visibility
    doesn't reflow (grow/shrink) the surrounding card. Public — reused across
    modules (e.g. main.py's OverviewPage) wherever a card is conditionally
    hidden but shouldn't shove its siblings when it disappears."""
    policy = widget.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    widget.setSizePolicy(policy)


class SummaryCard(QFrame):
    """The Overview page's P&L slab. A solid, fixed-height block that always
    shows all of its content — tabs, hero P&L, incoming/outgoing boxes,
    target/savings, and the weekly P&L breakdown. It never hides or collapses
    any section when the window shrinks: the right column it lives in is
    inside a scroll area (see OverviewPage), so a too-short window scrolls
    rather than dropping information."""

    def __init__(self, manager, doc, year, month, today):
        super().__init__()
        self.dm, self.doc = manager, doc
        self.year, self.month, self.today = year, month, today
        self.period = "Monthly"
        self.week_of_month: int | None = None
        self.range_doc = None       # set in week/range lens → headline shows range P&L
        self.currency = doc.get("currency", "$")
        self._hero_value = 0.0      # currently-displayed number, for count animation
        self._hero_anim = None

        self.setObjectName("Card")
        self.setStyleSheet(
            f"#Card{{background:transparent; border:none;}}")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14); root.setSpacing(0)

        self.tabs = SegTabBar(["Monthly", "Yearly", "YTD"], 0, kind="pill")
        self.tabs.changed.connect(self._period)
        tabrow = QHBoxLayout(); tabrow.addWidget(self.tabs); tabrow.addStretch(1)
        root.addLayout(tabrow)
        root.addSpacing(12)

        self.caption = label("", T.TEXT_MUTED, 11)
        root.addWidget(self.caption)
        self.hero = label("", T.GREEN_BRIGHT, 34, bold=True)
        root.addWidget(self.hero)
        self._vs_avg_lbl = label("", T.TEXT_DIM, 11)
        self._vs_avg_lbl.setVisible(False)
        retain_size(self._vs_avg_lbl)
        root.addWidget(self._vs_avg_lbl)
        self._bills_lbl = label("", T.TEXT_DIM, 11)
        self._bills_lbl.setVisible(False)
        retain_size(self._bills_lbl)
        root.addWidget(self._bills_lbl)
        root.addSpacing(10)

        boxes = QHBoxLayout(); boxes.setSpacing(28)
        self.box_in = StatBox("Incoming", "", T.GREEN)
        self.box_out = StatBox("Outgoing", "", T.RED)
        boxes.addWidget(self.box_in); boxes.addWidget(self.box_out)
        boxes.addStretch(1)
        root.addLayout(boxes)

        # --- collapsible section: target P&L + savings rate --------------
        self._targets_section = QWidget()
        tsec = QVBoxLayout(self._targets_section)
        tsec.setContentsMargins(0, 0, 0, 0); tsec.setSpacing(0)
        tsec.addSpacing(12); tsec.addWidget(hsep()); tsec.addSpacing(10)
        tgt = QHBoxLayout()
        tgt.addWidget(label("Target P&L", T.TEXT_MUTED, 12))
        tgt.addStretch(1)
        self.target_lbl = label("", T.TEXT, 12, bold=True)
        tgt.addWidget(self.target_lbl)
        tsec.addLayout(tgt)
        tsec.addSpacing(6)
        sav = QHBoxLayout()
        sav.addWidget(label("Savings rate:", T.TEXT_MUTED, 12))
        sav.addSpacing(4)
        self.savings_lbl = label("", T.ACCENT, 12, bold=True)
        sav.addWidget(self.savings_lbl); sav.addStretch(1)
        tsec.addLayout(sav)
        root.addWidget(self._targets_section)

        root.addSpacing(8)
        self._deficit_w = QFrame()
        self._deficit_w.setObjectName("DeficitBanner")
        self._deficit_w.setStyleSheet(
            f"#DeficitBanner{{background:{T.RED_BG};"
            f"border:1px solid {T.RED_BORDER};border-radius:4px;}}")
        _dl = QHBoxLayout(self._deficit_w)
        _dl.setContentsMargins(9, 6, 9, 6); _dl.setSpacing(6)
        _dl.addWidget(label("To break even", T.TEXT_MUTED, 11))
        _dl.addStretch(1)
        self._deficit_rate = label("", T.RED_BRIGHT, 12, bold=True)
        _dl.addWidget(self._deficit_rate)
        self._deficit_w.setVisible(False)
        retain_size(self._deficit_w)
        root.addWidget(self._deficit_w)

        # Reality check: bank-confirmed spend vs. the plan, right on the
        # "single glance" card — a plan/reality gap previously only showed
        # up in one small Analytics card, not here where PRODUCT.md says the
        # answer to "am I on track" should be visible without digging.
        root.addSpacing(6)
        self._reality_w = QFrame()
        self._reality_w.setObjectName("RealityBanner")
        self._reality_w.setStyleSheet(
            f"#RealityBanner{{background:{T.BG_CARD_SOFT};"
            f"border:1px solid {T.BORDER_LIGHT};border-radius:4px;}}")
        _rl = QHBoxLayout(self._reality_w)
        _rl.setContentsMargins(9, 6, 9, 6); _rl.setSpacing(6)
        _rl.addWidget(label("Bank says", T.TEXT_MUTED, 11))
        self._reality_lbl = label("", T.AMBER, 11, bold=True)
        _rl.addWidget(self._reality_lbl); _rl.addStretch(1)
        self._reality_w.setVisible(False)
        retain_size(self._reality_w)
        root.addWidget(self._reality_w)

        # --- collapsible section: weekly P&L breakdown --------------------
        self._weekly_section = QWidget()
        wsec = QVBoxLayout(self._weekly_section)
        wsec.setContentsMargins(0, 0, 0, 0); wsec.setSpacing(0)
        wsec.addSpacing(12); wsec.addWidget(hsep()); wsec.addSpacing(10)
        self.budget_hdr = label("", T.TEXT_MUTED, 9, bold=True)
        self.budget_hdr.setStyleSheet(
            f"color:{T.TEXT_MUTED}; background:transparent; letter-spacing:1px;")
        wsec.addWidget(self.budget_hdr)
        wsec.addSpacing(6)
        self.budget_box = QVBoxLayout(); self.budget_box.setSpacing(7)
        wsec.addLayout(self.budget_box)
        root.addWidget(self._weekly_section)

        self.refresh()
        # No fixed height and no collapsing: the card always sizes to its own
        # content. It stays "solid" against ephemeral toggles (deficit banner,
        # vs-avg comparison, bills strip) because those reserve their space via
        # retain_size above, so those never change its height. Real content
        # differences (e.g. a 4- vs 5-week month's breakdown) are allowed to
        # size it honestly, and the enclosing scroll area (see OverviewPage)
        # handles a window too short to show it all — by scrolling, never by
        # hiding a section.

    def set_context(self, doc, year, month):
        self.doc, self.year, self.month = doc, year, month
        self.currency = doc.get("currency", "$")
        self.week_of_month = None   # reset when month changes
        self.range_doc = None       # month lens → normal period machinery
        self.refresh()

    def set_range(self, range_doc, year, month):
        """Week/ISO-range lens: headline P&L comes straight from the range doc,
        the rest of the card stays anchored to the month for context."""
        self.range_doc = range_doc
        self.year, self.month = year, month
        self.doc = self.dm.load_month(year, month)   # month context for the lower half
        self.currency = range_doc.get("currency", "$")
        self.refresh()

    def set_week(self, week_of_month: int | None):
        self.week_of_month = week_of_month
        self.refresh()

    def _period(self, p):
        self.period = p
        self.refresh()

    def set_period(self, p):
        """Programmatically switch the period (also moves the tab highlight)."""
        self.tabs.set_active(p)
        self.period = p
        self.refresh()

    def _refresh_bills(self, range_mode):
        """The 'bills due / overdue this period' strip."""
        if not hasattr(self.dm, "items"):
            self._bills_lbl.setVisible(False); return
        if range_mode and self.range_doc.get("range_start"):
            rs = date.fromisoformat(self.range_doc["range_start"])
            re_ = date.fromisoformat(self.range_doc["range_end"])
        else:
            import calendar as _c
            last = _c.monthrange(self.year, self.month)[1]
            rs, re_ = date(self.year, self.month, 1), date(self.year, self.month, last)
        bs = B.bills_summary(self.dm.items(), rs, re_, self.today)
        cur = self.currency
        if not (bs["due_count"] or bs["paid_count"]):
            self._bills_lbl.setVisible(False); return
        parts = []
        if bs["due_count"]:
            parts.append(f"{bs['due_count']} bill{'s' if bs['due_count'] != 1 else ''} "
                         f"due {money(bs['due_total'], cur, signed=False)}")
        if bs["overdue"]:
            parts.append(f"{bs['overdue']} overdue")
        if bs["paid_count"]:
            parts.append(f"{bs['paid_count']} paid")
        self._bills_lbl.setText("  ·  ".join(parts))
        col = T.RED if bs["overdue"] else (T.AMBER if bs["due_count"] else T.GREEN)
        self._bills_lbl.setStyleSheet(f"color:{col}; background:transparent;")
        self._bills_lbl.setVisible(True)

    def refresh(self):
        cur = self.currency
        range_mode = self.range_doc is not None
        if range_mode:
            ri, re_ = B.income_total(self.range_doc), B.expense_total(self.range_doc)
            s = {"income": ri, "expenses": re_, "pnl": ri - re_}
            self.caption.setText(f"P&L — {self.range_doc.get('label', 'this week')}")
            wom = None
        else:
            wom = self.week_of_month if self.period == "Weekly" else None
            s = B.period_summary(self.dm, self.year, self.month, self.period, wom)
            self.caption.setText(f"{self.period} P&L — "
                                 f"{dm.MONTH_NAMES[self.month]} {self.year}")
        self.hero.setStyleSheet(
            f"color:{T.GREEN_BRIGHT if s['pnl'] >= 0 else T.RED};"
            f"background:transparent;")
        self._animate_hero(s["pnl"], cur)

        self._refresh_bills(range_mode)

        # vs-average comparison
        if range_mode:
            self._vs_avg_lbl.setVisible(False)
        elif self.period == "Monthly":
            hist = B.history(self.dm, self.year, self.month, 7)
            past = [v for _, v, is_cur in hist if not is_cur and v != 0]
            if len(past) >= 2:
                avg   = sum(past) / len(past)
                delta = s["pnl"] - avg
                arrow = "↑" if delta >= 0 else "↓"
                pct   = abs(delta / avg * 100) if avg else 0
                dcol  = T.GREEN if delta >= 0 else T.RED
                self._vs_avg_lbl.setText(
                    f"vs {len(past)}mo avg  {money(delta, cur)} ({arrow}{pct:.0f}%)")
                self._vs_avg_lbl.setStyleSheet(f"color:{dcol}; background:transparent;")
                self._vs_avg_lbl.setVisible(True)
            else:
                self._vs_avg_lbl.setVisible(False)
        elif self.period == "Weekly" and self.week_of_month:
            hist = B.history(self.dm, self.year, self.month, 6)
            past_vals = [v for _, v, is_cur in hist if not is_cur and v != 0]
            if len(past_vals) >= 2:
                n_wks = max(1, int(self.doc.get("weeks", 4)))
                avg_weekly = (sum(past_vals) / len(past_vals)) / n_wks
                delta = s["pnl"] - avg_weekly
                arrow = "↑" if delta >= 0 else "↓"
                pct   = abs(delta / avg_weekly * 100) if avg_weekly else 0
                dcol  = T.GREEN if delta >= 0 else T.RED
                self._vs_avg_lbl.setText(
                    f"vs avg week  {money(delta, cur)} ({arrow}{pct:.0f}%)")
                self._vs_avg_lbl.setStyleSheet(f"color:{dcol}; background:transparent;")
                self._vs_avg_lbl.setVisible(True)
            else:
                self._vs_avg_lbl.setVisible(False)
        else:
            self._vs_avg_lbl.setVisible(False)

        self.box_in.set_amount(money(s["income"], cur))
        self.box_out.set_amount(money(-s["expenses"], cur))

        self.target_lbl.setText(money(self.doc.get("target_pnl", 0), cur, signed=False))
        self.savings_lbl.setText(f"{B.savings_rate(self.doc) * 100:.1f}%")

        wb = B.weekly_budgets(self.doc)
        self.budget_hdr.setText("WEEKLY P&L")

        # ── deficit recovery rate ─────────────────────────────────────── #
        deficit_str = ""
        deficit = -s["pnl"]
        is_now = (self.year == self.today.year and self.month == self.today.month)
        if deficit > 0 and is_now and not range_mode:
            if self.period == "Weekly" and self.week_of_month:
                wr = next((r for r in wb["rows"] if r["week"] == self.week_of_month), None)
                if wr:
                    days_left = max(0, (wr["end"] - self.today).days + 1)
                    if days_left:
                        daily = deficit / days_left
                        s_pl = "s" if days_left != 1 else ""
                        deficit_str = (f"{money(daily, cur)}/day"
                                       f"  ({days_left} day{s_pl} left)")
            elif self.period == "Monthly":
                import calendar as _c
                days_in_mo = _c.monthrange(self.year, self.month)[1]
                days_left  = max(1, days_in_mo - self.today.day + 1)
                weekly = deficit / (days_left / 7.0)
                daily  = deficit / days_left
                deficit_str = (f"{money(weekly, cur)}/wk"
                               f"  ({money(daily, cur)}/day)")
            elif self.period in ("Yearly", "YTD"):
                from datetime import date as _d
                days_left = max(1, (_d(self.year, 12, 31) - self.today).days + 1)
                monthly = deficit / (days_left / 30.4375)
                weekly  = deficit / (days_left / 7.0)
                deficit_str = (f"{money(monthly, cur)}/mo"
                               f"  ({money(weekly, cur)}/wk)")
        self._deficit_rate.setText(deficit_str)
        self._deficit_w.setVisible(bool(deficit_str))
        # ─────────────────────────────────────────────────────────────── #

        # ── reality check: bank-confirmed spend vs. the plan ────────────── #
        reality_str, reality_col = "", T.TEXT_DIM
        if not range_mode and self.period == "Monthly":
            prefix = f"{self.year:04d}-{self.month:02d}"
            month_txns = [t for t in self.dm.transactions()
                         if t.get("date", "").startswith(prefix)]
            if month_txns:
                bank_expense = sum(-t["amount"] for t in month_txns if t["amount"] < 0)
                gap = bank_expense - s["expenses"]      # +ve = spent more than planned
                if abs(gap) > 0.005:
                    more_less = "more" if gap > 0 else "less"
                    reality_col = T.RED if gap > 0 else T.GREEN
                    reality_str = (f"{money(bank_expense, cur, signed=False)} spent "
                                   f"({money(abs(gap), cur, signed=False)} {more_less} "
                                   f"than planned)")
        self._reality_lbl.setText(reality_str)
        self._reality_lbl.setStyleSheet(f"color:{reality_col}; background:transparent;")
        self._reality_w.setVisible(bool(reality_str))
        # ─────────────────────────────────────────────────────────────── #

        clear_layout(self.budget_box)
        for wd in wb["rows"]:
            wk, start, end = wd["week"], wd["start"], wd["end"]
            active = (wom == wk)
            ws     = B.period_summary(self.dm, self.year, self.month, "Weekly", wk)
            wk_pnl = ws["pnl"]
            pnl_col = (T.GREEN if wk_pnl >= 0 else T.RED) if active else T.TEXT_DIM
            mn = dm.MONTH_ABBR[start.month]
            hrow = QHBoxLayout(); hrow.setSpacing(6)
            hrow.addWidget(label(f"Week {wk}", T.TEXT if active else T.TEXT_MUTED, 12, bold=active))
            hrow.addSpacing(6)
            hrow.addWidget(label(f"{mn} {start.day}–{end.day}", T.TEXT_DIM, 11))
            hrow.addStretch(1)
            hrow.addWidget(label(money(wk_pnl, cur), pnl_col, 12, bold=active))
            self.budget_box.addLayout(hrow)

    def _animate_hero(self, target, cur):
        """Count the hero P&L number from its old value to the new one
        instead of snapping — draws the eye to the one number this whole
        page exists to answer ("numbers lead", PRODUCT.md), more directly
        than animating chrome around it would."""
        start = self._hero_value
        if not ANIMATE or abs(target - start) < 0.005:
            self._hero_value = target
            self.hero.setText(money(target, cur))
            return
        if self._hero_anim:
            self._hero_anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(float(start)); anim.setEndValue(float(target))
        anim.setDuration(280)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _tick(v):
            self._hero_value = float(v)
            self.hero.setText(money(float(v), cur))
        anim.valueChanged.connect(_tick)
        self._hero_anim = anim
        anim.start()


# --------------------------------------------------------------------------- #
#  P&L line chart
# --------------------------------------------------------------------------- #
def _draw_chart_hover(p, geo, idx, plot, currency, color):
    """Shared hover overlay: guide line, ring marker and a value tooltip."""
    if idx is None or not (0 <= idx < len(geo)):
        return
    hx, hy, lab, val = geo[idx]
    gp = QPen(QColor(T.BORDER_LIGHT), 1, Qt.PenStyle.DashLine); gp.setDashPattern([2, 3])
    p.setPen(gp)
    p.drawLine(QPointF(hx, plot.top()), QPointF(hx, plot.bottom()))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    p.drawEllipse(QPointF(hx, hy), 4.0, 4.0)
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor("#ffffff"), 1.3))
    p.drawEllipse(QPointF(hx, hy), 6.5, 6.5)

    text = money(val, currency)
    f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(10)); f.setBold(True); p.setFont(f)
    tw = QFontMetrics(f).horizontalAdvance(text) + 16
    th = 21
    bx = min(max(hx - tw / 2, plot.left()), plot.right() - tw)
    by = hy - th - 9
    if by < plot.top():
        by = hy + 9
    rect = QRectF(bx, by, tw, th)
    p.setBrush(QColor(T.BG_CARD_SOFT)); p.setPen(QPen(QColor(T.BORDER_LIGHT), 1))
    p.drawRect(rect)
    p.setPen(QColor(color))
    p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)


class PnLChart(QWidget):
    def __init__(self):
        super().__init__()
        self.data = []          # [(label, value, is_current)]
        self.target = 0.0
        self.currency = "$"
        self._geo = []
        self._hover = None
        self.setMouseTracking(True)
        self.setMinimumHeight(150)

    def set_data(self, data, target, currency="$"):
        self.data = data
        self.target = target
        self.currency = currency
        self.update()

    def mouseMoveEvent(self, e):
        if not self._geo:
            return
        x = e.position().x()
        idx = min(range(len(self._geo)), key=lambda i: abs(self._geo[i][0] - x))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()

    def paintEvent(self, e):
        if not self.data:
            p = QPainter(self)
            draw_empty(p, self.rect(), "No months recorded yet")
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pad_l, pad_r, pad_t, pad_b = 38, 12, 10, 22
        w, h = self.width(), self.height()
        plot = QRectF(pad_l, pad_t, w - pad_l - pad_r, h - pad_t - pad_b)

        values = [v for _, v, _ in self.data]
        bot, top, step = _axis(values, self.target if self.target else None)

        def y_of(v):
            return plot.bottom() - (v - bot) / (top - bot) * plot.height()

        draw_axis(p, plot, bot, top, step, self.currency)

        n = len(self.data)
        xs = [plot.left() + (plot.width() * (i / (n - 1)) if n > 1 else plot.width()/2)
              for i in range(n)]

        # zero line (dotted yellow) — only when $0 is within the visible range
        if bot < 0 < top:
            zp = QPen(QColor(T.AMBER), 1.0, Qt.PenStyle.DotLine)
            p.setPen(zp)
            zy = y_of(0)
            p.drawLine(QPointF(plot.left(), zy), QPointF(plot.right(), zy))

        # P&L polyline
        line_pen = QPen(QColor(T.GREEN), 2)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(line_pen)
        pts = [QPointF(xs[i], y_of(values[i])) for i in range(n)]
        for i in range(n - 1):
            p.drawLine(pts[i], pts[i + 1])

        # markers + x labels
        f2 = QFont(T.FONT_FAMILY); f2.setPixelSize(T.scaled(9))
        for i, (lab, val, cur) in enumerate(self.data):
            p.setBrush(QColor(T.GREEN)); p.setPen(Qt.PenStyle.NoPen)
            r = 4.5 if cur else 3.0
            p.drawEllipse(pts[i], r, r)
            if cur:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(T.GREEN), 1.4))
                p.drawEllipse(pts[i], r + 3, r + 3)
            p.setFont(f2)
            p.setPen(QColor(T.TEXT if cur else T.TEXT_DIM))
            p.drawText(QRectF(xs[i] - 24, plot.bottom() + 5, 48, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       lab)

        self._geo = [(xs[i], pts[i].y(), self.data[i][0], values[i]) for i in range(n)]
        _draw_chart_hover(p, self._geo, self._hover, plot, self.currency, T.GREEN)


class ChartCard(QFrame):
    def __init__(self, manager, year, month, target):
        super().__init__()
        self.dm = manager
        self.setObjectName("Card")
        self.setStyleSheet(
            f"#Card{{background:transparent; border:none;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(8)
        lay.addWidget(label("P&L — Last 5 months", T.TEXT_MUTED, 11))
        self.chart = PnLChart()
        lay.addWidget(self.chart, 1)
        self.set_context(year, month, target)

    def set_context(self, year, month, target, currency="$"):
        # Fetch 6 months ending at current, then drop the current month so the
        # chart shows only the 5 completed months before the one being viewed.
        hist = B.history(self.dm, year, month, 6)
        self.chart.set_data([e for e in hist if not e[2]], target, currency)


class PredictedIncomeCard(QFrame):
    """Compact slab: next month's predicted income from recurring sources,
    compared against this month's actual income."""

    def __init__(self, doc, year, month, store=None):
        super().__init__()
        self.store = store
        self.setObjectName("Card")
        self.setStyleSheet(
            f"#Card{{background:transparent; border:none;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(label("PREDICTED INCOME — NEXT MONTH", T.TEXT_MUTED, 9, bold=True))
        hdr.addStretch(1)
        lay.addLayout(hdr)

        self.hero = label("", T.GREEN_BRIGHT, 26, bold=True)
        lay.addWidget(self.hero)

        self.delta_lbl = label("", T.TEXT_DIM, 11)
        lay.addWidget(self.delta_lbl)

        lay.addSpacing(4)
        self.sources_lbl = label("", T.TEXT_DIM, 10)
        self.sources_lbl.setWordWrap(True)
        lay.addWidget(self.sources_lbl)

        self.set_context(doc, year, month)

    def set_context(self, doc, year, month):
        cur = doc.get("currency", "$")
        idx = year * 12 + (month - 1) + 1
        ny, nm = idx // 12, idx % 12 + 1
        if self.store is not None:
            # Flat store projects recurrence forward, so next month's synth income
            # *is* the predicted income; compare against this month's synth income.
            ndoc = self.store.load_month(ny, nm)
            predicted = B.income_total(ndoc)
            current = B.income_total(self.store.load_month(year, month))
            breakdown = B.leaf_breakdown(ndoc, "income")
        else:
            predicted = B.predicted_income_for_month(doc, ny, nm)
            current = B.income_total(doc)
            breakdown = B.predicted_income_breakdown(doc, ny, nm)

        self.hero.setText(money(predicted, cur, signed=False))

        if current:
            delta = predicted - current
            arrow = "↑" if delta >= 0 else "↓"
            pct = abs(delta / current * 100)
            dcol = T.GREEN if delta >= 0 else T.RED
            self.delta_lbl.setText(
                f"vs this month: {money(delta, cur)} ({arrow}{pct:.0f}%)")
            self.delta_lbl.setStyleSheet(f"color:{dcol}; background:transparent;")
        else:
            self.delta_lbl.setText(f"vs this month ({money(current, cur, signed=False)})")
            self.delta_lbl.setStyleSheet(f"color:{T.TEXT_DIM}; background:transparent;")

        breakdown = [(n, a) for n, a in breakdown if a]
        if breakdown:
            n = len(breakdown)
            self.sources_lbl.setText(
                f"from {n} income source{'s' if n != 1 else ''}: " +
                ", ".join(name for name, _ in breakdown))
        else:
            self.sources_lbl.setText("No income sources next month")


# Category add / edit is now fully inline — see LedgerCard._start / _commit.


# --------------------------------------------------------------------------- #
#  General widgets used by the Analytics / Goals / History pages
# --------------------------------------------------------------------------- #
def _nice_step(rough: float) -> float:
    """Round a rough tick size up to a 1 / 2 / 2.5 / 5 × 10ⁿ value."""
    if rough <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(rough))
    for m in (1, 2, 2.5, 5, 10):
        if rough <= m * mag:
            return m * mag
    return 10 * mag


def _axis(values, target=None):
    vals = list(values) + ([target] if target else []) + [0.0]
    hi, lo = max(vals), min(vals)
    if hi == lo:
        hi += 1000
    step = _nice_step((hi - lo) / 4)
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def _tick_label(v, currency):
    if abs(v) >= 1000:
        return f"{currency}{v/1000:.0f}k"
    return f"{currency}{int(v)}"


def draw_axis(p, plot, bot, top, step, currency):
    """Horizontal gridlines + right-aligned tick labels in the left gutter."""
    # GRID (not BORDER_SOFT): the gridline should be the faintest ink on the
    # chart so the data line dominates — a flat demo trend shouldn't ship a
    # lattice louder than itself (critique §3.2, Henderson p80 #8).
    grid_pen = QPen(QColor(T.GRID), 1)
    f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(9)); p.setFont(f)
    tick = bot
    while tick <= top + 1e-6:
        y = plot.bottom() - (tick - bot) / (top - bot) * plot.height()
        p.setPen(grid_pen)
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(QColor(T.TEXT_DIM))
        p.drawText(QRectF(0, y - 7, plot.left() - 6, 14),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   _tick_label(tick, currency))
        tick += step


def draw_hover_pill(p, plot, x, y, lines):
    """Multi-line hover tooltip. ``lines`` = [(text, color, bold), …]; the pill
    is anchored above (x, y) and clamped inside ``plot``."""
    if not lines:
        return
    f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(10))
    fb = QFont(T.FONT_FAMILY); fb.setPixelSize(T.scaled(10)); fb.setBold(True)
    fm, fmb = QFontMetrics(f), QFontMetrics(fb)
    tw = max((fmb if b else fm).horizontalAdvance(t) for t, _, b in lines) + 16
    lh = 15
    th = lh * len(lines) + 7
    bx = min(max(x - tw / 2, plot.left()), plot.right() - tw)
    by = y - th - 9
    if by < plot.top():
        by = y + 9
    p.setBrush(QColor(T.BG_CARD_SOFT)); p.setPen(QPen(QColor(T.BORDER_LIGHT), 1))
    p.drawRect(QRectF(bx, by, tw, th))
    ty = by + 4
    for text, color, bold in lines:
        p.setFont(fb if bold else f)
        p.setPen(QColor(color))
        p.drawText(QRectF(bx, ty, tw, lh), int(Qt.AlignmentFlag.AlignCenter), text)
        ty += lh


def draw_empty(p, rect, msg):
    """Dim centred placeholder for charts with nothing to show."""
    f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(11)); p.setFont(f)
    p.setPen(QColor(T.TEXT_DIM))
    p.drawText(QRectF(rect), int(Qt.AlignmentFlag.AlignCenter), msg)


class _ChartLegendRow(QWidget):
    entered = pyqtSignal(int)
    left = pyqtSignal()

    def __init__(self, idx, color, name, value):
        super().__init__()
        self.idx = idx
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 1, 2, 1); lay.setSpacing(8)
        c = QFrame(); c.setFixedSize(9, 9)
        c.setStyleSheet(f"background:{color};")
        lay.addWidget(c)
        self._name = label(name, T.TEXT_MUTED, 11)
        lay.addWidget(self._name)
        lay.addStretch(1)
        if value:
            lay.addWidget(label(value, T.TEXT, 11))

    def set_active(self, on):
        self._name.setStyleSheet(
            f"color:{T.TEXT if on else T.TEXT_MUTED}; background:transparent;")

    def enterEvent(self, e):
        self.entered.emit(self.idx)

    def leaveEvent(self, e):
        self.left.emit()


class ChartLegend(QWidget):
    """Colour-chip legend rows, two-way hover synced with a chart."""
    hovered = pyqtSignal(int)   # row index; -1 = none

    def __init__(self):
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0); self._lay.setSpacing(1)
        self._rows: list[_ChartLegendRow] = []

    def set_rows(self, rows):
        """rows = [(color, name, value_str), …]"""
        while self._lay.count():
            it = self._lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows = []
        for i, (color, name, value) in enumerate(rows):
            r = _ChartLegendRow(i, color, name, value)
            r.entered.connect(self._enter)
            r.left.connect(lambda: self._enter(-1))
            self._lay.addWidget(r)
            self._rows.append(r)

    def _enter(self, idx):
        self.set_hover(idx)
        self.hovered.emit(idx)

    def set_hover(self, idx):
        for i, r in enumerate(self._rows):
            r.set_active(i == idx)


class Sparkline(QWidget):
    """Tiny axis-free trend line with a soft gradient fill and last-point dot."""

    def __init__(self, color=T.GREEN, height=34):
        super().__init__()
        self._values: list[float] = []
        self._color = color
        self.setFixedHeight(height)

    def set_values(self, values, color=None):
        self._values = [float(v) for v in values]
        if color:
            self._color = color
        self.update()

    def paintEvent(self, e):
        if len(self._values) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        lo, hi = min(self._values), max(self._values)
        if hi == lo:
            hi += 1.0
        n = len(self._values)
        pad = 3.0
        xs = [pad + (w - 2 * pad) * i / (n - 1) for i in range(n)]
        ys = [h - pad - (v - lo) / (hi - lo) * (h - 2 * pad)
              for v in self._values]
        pts = [QPointF(xs[i], ys[i]) for i in range(n)]

        grad = QLinearGradient(0, 0, 0, h)
        c = QColor(self._color); c.setAlpha(60); grad.setColorAt(0, c)
        c2 = QColor(self._color); c2.setAlpha(0); grad.setColorAt(1, c2)
        path = QPainterPath(QPointF(xs[0], h - pad))
        for pt in pts:
            path.lineTo(pt)
        path.lineTo(QPointF(xs[-1], h - pad))
        path.closeSubpath()
        p.fillPath(path, QBrush(grad))

        pen = QPen(QColor(self._color), 1.4)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        for i in range(n - 1):
            p.drawLine(pts[i], pts[i + 1])
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(self._color))
        p.drawEllipse(pts[-1], 2.4, 2.4)


class GroupedBarChart(QWidget):
    """Budget vs actual as horizontal bullet rows: hollow track = budget,
    filled bar = actual (green under / amber near / red over, with an overrun
    tail past the budget tick)."""
    hovered = pyqtSignal(int)   # row index; -1 = none

    ROW_H = 28
    LABEL_W = 118
    VALUE_W = 118

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[str, float, float]] = []   # (name, budget, actual)
        self.currency = "$"
        self._hover = -1
        self._reveal = 1.0
        self._anim = None
        self.setMouseTracking(True)
        self.setMinimumHeight(self.ROW_H + 8)

    def set_data(self, rows, currency="$"):
        self.rows = rows
        self.currency = currency
        self._hover = -1
        self.setFixedHeight(max(1, len(rows)) * self.ROW_H + 8)
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def _row_at(self, y):
        idx = int((y - 4) // self.ROW_H)
        return idx if 0 <= idx < len(self.rows) else -1

    def mouseMoveEvent(self, e):
        idx = self._row_at(e.position().y())
        if idx != self._hover:
            self._hover = idx
            self.hovered.emit(idx)
            self.update()

    def leaveEvent(self, e):
        if self._hover != -1:
            self._hover = -1
            self.hovered.emit(-1)
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.rows:
            draw_empty(p, self.rect(), "No budgeted categories yet")
            return
        maxv = max(max(b, a) for _, b, a in self.rows) or 1.0
        bar_x = self.LABEL_W
        bar_w = max(10.0, self.width() - self.LABEL_W - self.VALUE_W)
        f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(11))
        fs = QFont(T.FONT_FAMILY); fs.setPixelSize(T.scaled(10))

        for i, (name, budget, actual) in enumerate(self.rows):
            y0 = 4 + i * self.ROW_H
            cy = y0 + self.ROW_H / 2
            if i == self._hover:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(T.BG_HOVER))
                p.drawRect(QRectF(0, y0, self.width(), self.ROW_H))

            # category label
            p.setFont(f)
            p.setPen(QColor(T.TEXT if i == self._hover else T.TEXT_MUTED))
            p.drawText(QRectF(0, y0, self.LABEL_W - 10, self.ROW_H),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       name if len(name) <= 16 else name[:15] + "…")

            bw_budget = budget / maxv * bar_w
            bw_actual = actual / maxv * bar_w * self._reveal

            # hollow budget track
            if budget > 0:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(T.BORDER_LIGHT), 1))
                p.drawRect(QRectF(bar_x, cy - 5, bw_budget, 10))

            # actual fill (colour by pace)
            if actual > 0:
                ratio = actual / budget if budget else 2.0
                col = (T.GREEN if ratio < 0.85
                       else T.AMBER if ratio <= 1.0 else T.RED)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(col))
                p.drawRect(QRectF(bar_x, cy - 5,
                                  min(bw_actual, bw_budget) if budget else bw_actual, 10))
                if budget and bw_actual > bw_budget:      # overrun tail
                    tail = QColor(T.RED); tail.setAlpha(160)
                    p.setBrush(tail)
                    p.drawRect(QRectF(bar_x + bw_budget, cy - 5,
                                      bw_actual - bw_budget, 10))

            # budget tick
            if budget > 0:
                p.setPen(QPen(QColor(T.AMBER), 1.4))
                p.drawLine(QPointF(bar_x + bw_budget, cy - 8),
                           QPointF(bar_x + bw_budget, cy + 8))

            # value text
            p.setFont(fs)
            p.setPen(QColor(T.TEXT if i == self._hover else T.TEXT_DIM))
            pct = f"  ({actual / budget * 100:.0f}%)" if budget else ""
            p.drawText(QRectF(self.width() - self.VALUE_W + 6, y0,
                              self.VALUE_W - 8, self.ROW_H),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       f"{money(actual, self.currency, signed=False)} / "
                       f"{money(budget, self.currency, signed=False)}{pct}")


class StackedBarChart(QWidget):
    """Monthly expense composition as stacked vertical bars, one segment per
    category (T.SERIES colours), with per-segment hover."""
    hovered = pyqtSignal(int, int)   # (month_idx, cat_idx); (-1, -1) = none

    def __init__(self):
        super().__init__()
        self.labels: list[str] = []
        self.categories: list[str] = []
        self.matrix: list[list[float]] = []     # matrix[m][c]
        self.colors: list[str] = []
        self.currency = "$"
        self._geo = []                          # [(QRectF, m, c)]
        self._hover = (-1, -1)
        self._hover_cat = -1                    # legend-driven highlight
        self._reveal = 1.0
        self._anim = None
        self.setMouseTracking(True)
        self.setMinimumHeight(200)

    def set_data(self, labels, categories, matrix, colors=None, currency="$"):
        self.labels = labels
        self.categories = categories
        self.matrix = matrix
        self.colors = colors or [T.category_color(name) for name in categories]
        self.currency = currency
        self._hover = (-1, -1)
        self._hover_cat = -1
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def set_hover_cat(self, cat_idx: int):
        if cat_idx != self._hover_cat:
            self._hover_cat = cat_idx
            self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        hit = (-1, -1)
        for rect, m, c in self._geo:
            if rect.contains(pos):
                hit = (m, c)
                break
        if hit != self._hover:
            self._hover = hit
            self.hovered.emit(*hit)
            self.update()

    def leaveEvent(self, e):
        if self._hover != (-1, -1):
            self._hover = (-1, -1)
            self.hovered.emit(-1, -1)
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        totals = [sum(row) for row in self.matrix]
        if not self.matrix or not any(totals):
            draw_empty(p, self.rect(), "No expenses in this period")
            return
        pad_l, pad_r, pad_t, pad_b = 44, 14, 12, 24
        plot = QRectF(pad_l, pad_t, self.width() - pad_l - pad_r,
                      self.height() - pad_t - pad_b)
        bot, top, step = _axis(totals)
        bot = 0.0
        draw_axis(p, plot, bot, top, step, self.currency)

        def y_of(v):
            return plot.bottom() - (v - bot) / (top - bot) * plot.height()

        n = len(self.matrix)
        slot = plot.width() / n
        bw = slot * 0.56
        self._geo = []
        f2 = QFont(T.FONT_FAMILY); f2.setPixelSize(T.scaled(9))
        for m, row in enumerate(self.matrix):
            x = plot.left() + slot * m + (slot - bw) / 2
            acc = 0.0
            for c, v in enumerate(row):
                if v <= 0:
                    continue
                y1, y0 = y_of(acc * self._reveal), y_of((acc + v) * self._reveal)
                rect = QRectF(x, y0, bw, y1 - y0)
                col = QColor(self.colors[c % len(self.colors)])
                if (m, c) == self._hover or c == self._hover_cat:
                    col = col.lighter(130)
                elif self._hover_cat != -1 or self._hover != (-1, -1):
                    col.setAlpha(120)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(col)
                p.drawRect(rect)
                self._geo.append((rect, m, c))
                acc += v
            p.setFont(f2)
            p.setPen(QColor(T.TEXT if m == n - 1 else T.TEXT_DIM))
            p.drawText(QRectF(plot.left() + slot * m, plot.bottom() + 5, slot, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       self.labels[m] if m < len(self.labels) else "")

        hm, hc = self._hover
        if hm >= 0:
            v = self.matrix[hm][hc]
            tot = totals[hm] or 1.0
            rect = next(r for r, m, c in self._geo if (m, c) == (hm, hc))
            draw_hover_pill(
                p, plot, rect.center().x(), rect.top(),
                [(self.categories[hc], T.TEXT_MUTED, False),
                 (f"{money(v, self.currency, signed=False)}  ·  "
                  f"{v / tot * 100:.0f}%", T.TEXT, True)])


class CalendarHeatmap(QWidget):
    """Month grid: cell shade = spend that day (bank transactions), amber dot =
    bill due, green dot = income lands, ring = today."""
    day_clicked = pyqtSignal(object)   # datetime.date

    def __init__(self):
        super().__init__()
        self.year = self.month = 0
        self.spend: dict[int, float] = {}
        self.due_days: dict[int, list[str]] = {}
        self.income_days: set[int] = set()
        self.today = None
        self.currency = "$"
        self._hover = -1        # day number, -1 = none
        self._cells: list[tuple[QRectF, int]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(230)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_month(self, year, month, spend, due_days, income_days,
                  today=None, currency="$"):
        self.year, self.month = year, month
        self.spend = spend
        self.due_days = due_days
        self.income_days = income_days
        self.today = today
        self.currency = currency
        self._hover = -1
        self.update()

    def _day_at(self, pos):
        for rect, day in self._cells:
            if rect.contains(pos):
                return day
        return -1

    def mouseMoveEvent(self, e):
        d = self._day_at(e.position())
        if d != self._hover:
            self._hover = d
            self.update()

    def leaveEvent(self, e):
        if self._hover != -1:
            self._hover = -1
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            d = self._day_at(e.position())
            if d > 0:
                self.day_clicked.emit(date(self.year, self.month, d))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.year:
            draw_empty(p, self.rect(), "No month selected")
            return
        import calendar as _cal
        first_wd, n_days = _cal.monthrange(self.year, self.month)   # Mon = 0
        n_weeks = math.ceil((first_wd + n_days) / 7)

        pad = 4
        head_h = 16
        gap = 3
        cw = (self.width() - 2 * pad - gap * 6) / 7
        ch = (self.height() - 2 * pad - head_h - gap * (n_weeks - 1)) / n_weeks

        f9 = QFont(T.FONT_FAMILY); f9.setPixelSize(T.scaled(9))
        p.setFont(f9); p.setPen(QColor(T.TEXT_DIM))
        for i, wd in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            p.drawText(QRectF(pad + i * (cw + gap), pad, cw, head_h - 2),
                       int(Qt.AlignmentFlag.AlignCenter), wd)

        # Structure comes from faint week-row separators + the weekday headers,
        # not from 42 filled boxes (which was a wall of identical grey rectangles
        # the eye had to scan to find the ~3 meaningful cells — Filipiuk p34/p35).
        # Only cells that carry data (spend, hover, today) get any fill/ink now.
        p.setPen(QPen(QColor(T.BORDER_SOFT), 1))
        for r in range(1, n_weeks):
            sy = pad + head_h + r * (ch + gap) - gap / 2
            p.drawLine(QPointF(pad, sy), QPointF(self.width() - pad, sy))

        vmax = max(self.spend.values(), default=0.0) or 1.0
        self._cells = []
        for day in range(1, n_days + 1):
            slot = first_wd + day - 1
            r, c = divmod(slot, 7)
            rect = QRectF(pad + c * (cw + gap), pad + head_h + r * (ch + gap),
                          cw, ch)
            self._cells.append((rect, day))

            p.setPen(Qt.PenStyle.NoPen)
            amt = self.spend.get(day, 0.0)
            if amt > 0:                                 # spend = the one fill that
                fill = QColor(T.RED)                    # carries data — rounded,
                fill.setAlpha(int(35 + 170 * min(1.0, amt / vmax)))
                p.setBrush(fill)
                p.drawRoundedRect(rect, T.RADIUS_SM, T.RADIUS_SM)
            if day == self._hover:
                hl = QColor(T.BG_HOVER); hl.setAlpha(120)
                p.setBrush(hl); p.drawRoundedRect(rect, T.RADIUS_SM, T.RADIUS_SM)

            # day number
            p.setFont(f9)
            p.setPen(QColor(T.TEXT_MUTED))
            p.drawText(rect.adjusted(4, 2, -2, 0),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                       str(day))

            # due / income dots (bottom-right corner)
            dx = rect.right() - 7
            p.setPen(Qt.PenStyle.NoPen)
            if day in self.due_days:
                p.setBrush(QColor(T.AMBER))
                p.drawEllipse(QPointF(dx, rect.bottom() - 6), 2.4, 2.4)
                dx -= 7
            if day in self.income_days:
                p.setBrush(QColor(T.GREEN))
                p.drawEllipse(QPointF(dx, rect.bottom() - 6), 2.4, 2.4)

            # today ring — now the only outlined cell, so it genuinely stands out
            if (self.today and self.today.year == self.year
                    and self.today.month == self.month and self.today.day == day):
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(T.GREEN), 1.4))
                p.drawRoundedRect(rect.adjusted(0.7, 0.7, -0.7, -0.7),
                                  T.RADIUS_SM, T.RADIUS_SM)

        if self._hover > 0:
            rect = next(r for r, d in self._cells if d == self._hover)
            amt = self.spend.get(self._hover, 0.0)
            lines = [(date(self.year, self.month, self._hover).strftime("%a %d %b"),
                      T.TEXT_MUTED, False),
                     (money(amt, self.currency, signed=False) + " spent",
                      T.RED if amt else T.TEXT_DIM, True)]
            for nm in self.due_days.get(self._hover, [])[:3]:
                lines.append((f"due: {nm}", T.AMBER, False))
            draw_hover_pill(p, QRectF(self.rect()), rect.center().x(), rect.top(),
                            lines)


class FanChart(QWidget):
    """Liquid-balance forecast: solid history, dashed median projection, a
    translucent uncertainty band, red shading below zero and an amber zero
    line."""

    def __init__(self):
        super().__init__()
        self.history: list[tuple[str, float]] = []
        self.band: list[dict] = []          # [{label, median, lo, hi}]
        self.currency = "$"
        self._geo = []                      # [(x, y, label, value, lo, hi)]
        self._hover = None
        self._reveal = 1.0
        self._anim = None
        self.setMouseTracking(True)
        self.setMinimumHeight(180)

    def set_data(self, history, band, currency="$"):
        self.history = history
        self.band = band
        self.currency = currency
        self._hover = None
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def mouseMoveEvent(self, e):
        if not self._geo:
            return
        x = e.position().x()
        idx = min(range(len(self._geo)), key=lambda i: abs(self._geo[i][0] - x))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._reveal)
        if not self.history and not self.band:
            draw_empty(p, self.rect(), "No accounts to forecast — add one in Settings")
            return
        pad_l, pad_r, pad_t, pad_b = 44, 14, 12, 24
        plot = QRectF(pad_l, pad_t, self.width() - pad_l - pad_r,
                      self.height() - pad_t - pad_b)

        hvals = [v for _, v in self.history]
        bvals = ([b["hi"] for b in self.band] + [b["lo"] for b in self.band]
                 + [b["median"] for b in self.band])
        bot, top, step = _axis(hvals + bvals)
        draw_axis(p, plot, bot, top, step, self.currency)

        def y_of(v):
            return plot.bottom() - (v - bot) / (top - bot) * plot.height()

        n = len(self.history) + len(self.band)
        xs = [plot.left() + (plot.width() * i / (n - 1) if n > 1 else plot.width() / 2)
              for i in range(n)]

        # zero line
        if bot < 0 < top:
            zp = QPen(QColor(T.AMBER), 1.0, Qt.PenStyle.DotLine); p.setPen(zp)
            p.drawLine(QPointF(plot.left(), y_of(0)), QPointF(plot.right(), y_of(0)))

        nh = len(self.history)
        hist_pts = [QPointF(xs[i], y_of(hvals[i])) for i in range(nh)]

        # forecast band polygon (starts at the last history point)
        if self.band:
            join_x = xs[nh - 1] if nh else xs[0]
            join_y = y_of(hvals[-1]) if nh else y_of(self.band[0]["median"])
            hi_pts = [QPointF(join_x, join_y)]
            lo_pts = [QPointF(join_x, join_y)]
            med_pts = [QPointF(join_x, join_y)]
            for j, b in enumerate(self.band):
                x = xs[nh + j]
                hi_pts.append(QPointF(x, y_of(b["hi"])))
                lo_pts.append(QPointF(x, y_of(b["lo"])))
                med_pts.append(QPointF(x, y_of(b["median"])))
            band_path = QPainterPath(hi_pts[0])
            for pt in hi_pts[1:]:
                band_path.lineTo(pt)
            for pt in reversed(lo_pts):
                band_path.lineTo(pt)
            band_path.closeSubpath()
            bc = QColor(T.ACCENT); bc.setAlpha(45)
            p.fillPath(band_path, QBrush(bc))

            # red shading where the band dips below zero
            if bot < 0 < top:
                clip = QPainterPath()
                clip.addRect(QRectF(plot.left(), y_of(0), plot.width(),
                                    plot.bottom() - y_of(0)))
                p.save(); p.setClipPath(clip)
                rc = QColor(T.RED); rc.setAlpha(70)
                p.fillPath(band_path, QBrush(rc))
                p.restore()

            # dashed median
            mp = QPen(QColor(T.ACCENT), 1.8, Qt.PenStyle.DashLine)
            mp.setDashPattern([4, 3]); p.setPen(mp)
            for i in range(len(med_pts) - 1):
                p.drawLine(med_pts[i], med_pts[i + 1])

        # solid history line
        if nh:
            pen = QPen(QColor(T.GREEN), 2); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            for i in range(nh - 1):
                p.drawLine(hist_pts[i], hist_pts[i + 1])
            p.setBrush(QColor(T.GREEN)); p.setPen(Qt.PenStyle.NoPen)
            for pt in hist_pts:
                p.drawEllipse(pt, 3.0, 3.0)

        # x labels
        f2 = QFont(T.FONT_FAMILY); f2.setPixelSize(T.scaled(9)); p.setFont(f2)
        self._geo = []
        for i in range(nh):
            lab, val = self.history[i]
            self._geo.append((xs[i], hist_pts[i].y(), lab, val, val, val))
            p.setPen(QColor(T.TEXT_DIM))
            p.drawText(QRectF(xs[i] - 24, plot.bottom() + 5, 48, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), lab)
        for j, b in enumerate(self.band):
            x = xs[nh + j]
            self._geo.append((x, y_of(b["median"]), b["label"], b["median"],
                              b["lo"], b["hi"]))
            p.setPen(QColor(T.TEXT_MUTED))
            p.drawText(QRectF(x - 24, plot.bottom() + 5, 48, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), b["label"])

        if self._hover is not None and 0 <= self._hover < len(self._geo):
            hx, hy, lab, val, lo, hi = self._geo[self._hover]
            gp = QPen(QColor(T.BORDER_LIGHT), 1, Qt.PenStyle.DashLine)
            gp.setDashPattern([2, 3]); p.setPen(gp)
            p.drawLine(QPointF(hx, plot.top()), QPointF(hx, plot.bottom()))
            lines = [(money(val, self.currency), T.TEXT, True)]
            if hi > lo:
                lines.append((f"{money(lo, self.currency)} – {money(hi, self.currency)}",
                              T.TEXT_MUTED, False))
            draw_hover_pill(p, plot, hx, hy, lines)


class AreaChart(QWidget):
    """Net-worth over time: assets as a green area above the baseline,
    liabilities as a red area below it, net worth as a bright line."""

    def __init__(self):
        super().__init__()
        self.series: list[dict] = []        # [{label, assets, liabilities, net}]
        self.currency = "$"
        self._geo = []
        self._hover = None
        self._reveal = 1.0
        self._anim = None
        self.setMouseTracking(True)
        self.setMinimumHeight(180)

    def set_data(self, series, currency="$"):
        self.series = series
        self.currency = currency
        self._hover = None
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def mouseMoveEvent(self, e):
        if not self._geo:
            return
        x = e.position().x()
        idx = min(range(len(self._geo)), key=lambda i: abs(self._geo[i][0] - x))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._reveal)
        if not self.series:
            draw_empty(p, self.rect(), "No net-worth history yet")
            return
        pad_l, pad_r, pad_t, pad_b = 46, 14, 12, 24
        plot = QRectF(pad_l, pad_t, self.width() - pad_l - pad_r,
                      self.height() - pad_t - pad_b)
        assets = [s["assets"] for s in self.series]
        liabs = [-s["liabilities"] for s in self.series]
        bot, top, step = _axis(assets + liabs)
        draw_axis(p, plot, bot, top, step, self.currency)

        def y_of(v):
            return plot.bottom() - (v - bot) / (top - bot) * plot.height()

        n = len(self.series)
        xs = [plot.left() + (plot.width() * i / (n - 1) if n > 1 else plot.width() / 2)
              for i in range(n)]
        base_y = y_of(0) if bot < 0 < top else plot.bottom()

        def area(vals, color, alpha):
            if n < 2:
                return
            grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
            c = QColor(color); c.setAlpha(alpha); grad.setColorAt(0, c)
            c2 = QColor(color); c2.setAlpha(0); grad.setColorAt(1, c2)
            path = QPainterPath(QPointF(xs[0], base_y))
            for i in range(n):
                path.lineTo(QPointF(xs[i], y_of(vals[i])))
            path.lineTo(QPointF(xs[-1], base_y)); path.closeSubpath()
            p.fillPath(path, QBrush(grad))

        area(assets, T.GREEN, 70)
        if any(s["liabilities"] for s in self.series):
            # liabilities dip below the baseline (drawn from base downward)
            grad = QLinearGradient(0, base_y, 0, plot.bottom())
            c = QColor(T.RED); c.setAlpha(70); grad.setColorAt(0, c)
            c2 = QColor(T.RED); c2.setAlpha(0); grad.setColorAt(1, c2)
            path = QPainterPath(QPointF(xs[0], base_y))
            for i in range(n):
                path.lineTo(QPointF(xs[i], y_of(liabs[i])))
            path.lineTo(QPointF(xs[-1], base_y)); path.closeSubpath()
            p.fillPath(path, QBrush(grad))

        # net line
        nets = [s["net"] for s in self.series]
        pen = QPen(QColor(T.GREEN_BRIGHT), 2); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        npts = [QPointF(xs[i], y_of(nets[i])) for i in range(n)]
        for i in range(n - 1):
            p.drawLine(npts[i], npts[i + 1])
        p.setBrush(QColor(T.GREEN_BRIGHT)); p.setPen(Qt.PenStyle.NoPen)
        for pt in npts:
            p.drawEllipse(pt, 3.0, 3.0)

        f2 = QFont(T.FONT_FAMILY); f2.setPixelSize(T.scaled(9)); p.setFont(f2)
        self._geo = []
        for i, s in enumerate(self.series):
            self._geo.append((xs[i], npts[i].y(), s))
            p.setPen(QColor(T.TEXT if i == n - 1 else T.TEXT_DIM))
            p.drawText(QRectF(xs[i] - 24, plot.bottom() + 5, 48, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       s["label"])

        if self._hover is not None and 0 <= self._hover < len(self._geo):
            hx, hy, s = self._geo[self._hover]
            gp = QPen(QColor(T.BORDER_LIGHT), 1, Qt.PenStyle.DashLine)
            gp.setDashPattern([2, 3]); p.setPen(gp)
            p.drawLine(QPointF(hx, plot.top()), QPointF(hx, plot.bottom()))
            draw_hover_pill(p, plot, hx, hy, [
                (f"Net {money(s['net'], self.currency)}", T.GREEN_BRIGHT, True),
                (f"Assets {money(s['assets'], self.currency, signed=False)}", T.GREEN, False),
                (f"Debt {money(s['liabilities'], self.currency, signed=False)}", T.RED, False)])


class SubscriptionTimeline(QWidget):
    """Horizontal date axis of upcoming renewals; each marker's radius scales
    with amount, colour keyed per subscription, staggered to avoid overlap."""

    def __init__(self):
        super().__init__()
        self.items: list[dict] = []     # [{name, next(iso), days_until, amount, type}]
        self.days = 60
        self.currency = "$"
        self._geo = []                  # [(cx, cy, r, item)]
        self._hover = -1
        self._reveal = 1.0
        self._anim = None
        self.setMouseTracking(True)
        self.setMinimumHeight(110)

    def set_data(self, items, days=60, currency="$"):
        self.items = items
        self.days = days
        self.currency = currency
        self._hover = -1
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        hit = -1
        for i, (cx, cy, r, _it) in enumerate(self._geo):
            if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= (r + 2) ** 2:
                hit = i
        if hit != self._hover:
            self._hover = hit
            self.update()

    def leaveEvent(self, e):
        if self._hover != -1:
            self._hover = -1
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._reveal)
        if not self.items:
            draw_empty(p, self.rect(), "No renewals in the next 60 days")
            return
        pad_l, pad_r = 16, 16
        axis_y = self.height() - 22
        x0, x1 = pad_l, self.width() - pad_r

        # axis
        p.setPen(QPen(QColor(T.BORDER_LIGHT), 1))
        p.drawLine(QPointF(x0, axis_y), QPointF(x1, axis_y))
        f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(9)); p.setFont(f)
        for frac, lab in ((0, "today"), (0.5, f"+{self.days // 2}d"),
                          (1.0, f"+{self.days}d")):
            x = x0 + (x1 - x0) * frac
            p.setPen(QColor(T.BORDER_SOFT))
            p.drawLine(QPointF(x, axis_y - 3), QPointF(x, axis_y + 3))
            p.setPen(QColor(T.TEXT_DIM))
            p.drawText(QRectF(x - 24, axis_y + 5, 48, 12),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), lab)

        amax = max(i["amount"] for i in self.items) or 1.0
        self._geo = []
        for k, it in enumerate(self.items):
            frac = min(1.0, max(0.0, it["days_until"] / self.days))
            cx = x0 + (x1 - x0) * frac
            r = 4 + 10 * math.sqrt(it["amount"] / amax)
            cy = axis_y - 16 - (k % 3) * 22          # stagger three rows
            color = T.GREEN if it.get("type") == "income" else T.category_color(it.get("name", ""))
            # stem
            p.setPen(QPen(QColor(T.BORDER_SOFT), 1))
            p.drawLine(QPointF(cx, cy), QPointF(cx, axis_y))
            c = QColor(color)
            if k == self._hover:
                c = c.lighter(130)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(c)
            p.drawEllipse(QPointF(cx, cy), r, r)
            self._geo.append((cx, cy, r, it))

        if self._hover != -1:
            cx, cy, r, it = self._geo[self._hover]
            d = date.fromisoformat(it["next"])
            when = "today" if it["days_until"] == 0 else f"in {it['days_until']}d"
            draw_hover_pill(p, QRectF(self.rect()), cx, cy - r, [
                (it["name"], T.TEXT, True),
                (f"{d.strftime('%d %b')} · {when}", T.TEXT_MUTED, False),
                (money(it["amount"], self.currency, signed=False, cents=True),
                 T.GREEN if it.get("type") == "income" else T.RED, False)])


class LineChart(QWidget):
    """Auto-scaling line chart: optional dashed target line and area fill.
    Clicking a data point emits ``clicked_idx``; set_selected() marks a point."""
    clicked_idx = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.points = []          # [(label, value)]
        self.target = None
        self.fill = False
        self.highlight_last = True
        self.currency = "$"
        self.color = T.GREEN
        self._geo = []
        self._hover = None
        self._selected: int | None = None
        self._reveal = 1.0
        self._anim = None
        self.setMouseTracking(True)
        self.setMinimumHeight(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_series(self, points, target=None, fill=False,
                   highlight_last=True, currency="$", color=None):
        self.points = points
        self.target = target
        self.fill = fill
        self.highlight_last = highlight_last
        self.currency = currency
        if color:
            self.color = color
        self._selected = None
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def set_selected(self, idx: int | None):
        self._selected = idx
        self.update()

    def set_secondary_series(self, points, color=None):
        self._secondary = points
        self._secondary_color = color or T.RED
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._geo:
            x = e.position().x()
            idx = min(range(len(self._geo)), key=lambda i: abs(self._geo[i][0] - x))
            self._selected = idx
            self.clicked_idx.emit(idx)
            self.update()

    def mouseMoveEvent(self, e):
        if not self._geo:
            return
        x = e.position().x()
        idx = min(range(len(self._geo)), key=lambda i: abs(self._geo[i][0] - x))
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()

    def paintEvent(self, e):
        if not self.points:
            p = QPainter(self)
            draw_empty(p, self.rect(), "No data to chart yet")
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._reveal)
        pad_l, pad_r, pad_t, pad_b = 44, 14, 12, 24
        plot = QRectF(pad_l, pad_t, self.width() - pad_l - pad_r,
                      self.height() - pad_t - pad_b)
        values = [v for _, v in self.points]
        sec = getattr(self, '_secondary', [])
        all_vals = values + [v for _, v in sec]
        bot, top, step = _axis(all_vals, self.target)

        def y_of(v):
            return plot.bottom() - (v - bot) / (top - bot) * plot.height()

        draw_axis(p, plot, bot, top, step, self.currency)

        n = len(self.points)
        xs = [plot.left() + (plot.width() * i / (n - 1) if n > 1 else plot.width() / 2)
              for i in range(n)]
        pts = [QPointF(xs[i], y_of(values[i])) for i in range(n)]

        if self.fill and n > 1:
            grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
            c = QColor(self.color); c.setAlpha(70); grad.setColorAt(0, c)
            c2 = QColor(self.color); c2.setAlpha(0); grad.setColorAt(1, c2)
            path = QPainterPath(QPointF(xs[0], plot.bottom()))
            for pt in pts:
                path.lineTo(pt)
            path.lineTo(QPointF(xs[-1], plot.bottom()))
            path.closeSubpath()
            p.fillPath(path, QBrush(grad))

        if self.target:
            tp = QPen(QColor(T.AMBER), 1.4, Qt.PenStyle.DashLine)
            tp.setDashPattern([2, 3]); p.setPen(tp)
            p.drawLine(QPointF(plot.left(), y_of(self.target)),
                       QPointF(plot.right(), y_of(self.target)))

        pen = QPen(QColor(self.color), 2); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        for i in range(n - 1):
            p.drawLine(pts[i], pts[i + 1])

        f2 = QFont(T.FONT_FAMILY); f2.setPixelSize(T.scaled(9))
        for i, (lab, _) in enumerate(self.points):
            cur = self.highlight_last and i == n - 1
            p.setBrush(QColor(self.color)); p.setPen(Qt.PenStyle.NoPen)
            r = 4.5 if cur else 3.0
            p.drawEllipse(pts[i], r, r)
            if cur:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(self.color), 1.4))
                p.drawEllipse(pts[i], r + 3, r + 3)
            p.setFont(f2)
            p.setPen(QColor(T.TEXT if cur else T.TEXT_DIM))
            p.drawText(QRectF(xs[i] - 26, plot.bottom() + 5, 52, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       lab)

        # secondary series (e.g. expenses)
        if sec:
            sec_vals = [v for _, v in sec]
            sec_pts = [QPointF(plot.left() + (plot.width() * i / (max(len(sec_vals)-1, 1))
                               if len(sec_vals) > 1 else plot.width() / 2),
                               y_of(sec_vals[i]))
                       for i in range(len(sec_vals))]
            sec_col = getattr(self, '_secondary_color', T.RED)
            pen2 = QPen(QColor(sec_col), 2); pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen2)
            for i in range(len(sec_pts) - 1):
                p.drawLine(sec_pts[i], sec_pts[i + 1])
            p.setBrush(QColor(sec_col)); p.setPen(Qt.PenStyle.NoPen)
            for pt in sec_pts:
                p.drawEllipse(pt, 3.0, 3.0)

        # Selected-point ring (drawn on top of regular markers)
        if self._selected is not None and 0 <= self._selected < len(pts):
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(self.color), 1.8))
            p.drawEllipse(pts[self._selected], 8.0, 8.0)

        self._geo = [(xs[i], pts[i].y(), self.points[i][0], values[i]) for i in range(n)]
        _draw_chart_hover(p, self._geo, self._hover, plot, self.currency, self.color)


class DonutChart(QWidget):
    """Proportional ring with a value in the hole.
    Hover a segment to highlight it and see its name + % in the centre."""
    hovered = pyqtSignal(int)   # segment index; -1 = none

    def __init__(self, hole_bg=T.BG_CARD):
        super().__init__()
        self.segments = []        # [(value, color)]
        self._names: list[str] = []
        self.center_top = ""
        self.center_sub = ""
        self.hole_bg = hole_bg
        self._hover = -1
        self._reveal = 1.0
        self._anim = None
        self.setMinimumSize(160, 160)
        self.setMouseTracking(True)

    def set_segments(self, segments, center_top="", center_sub="", names=None):
        self.segments = segments
        self._names = names or [""] * len(segments)
        self.center_top = center_top
        self.center_sub = center_sub
        self._hover = -1
        self._anim = _reveal_anim(self)
        if self._anim:
            self._reveal = 0.0
            self._anim.start()
        self.update()

    def set_hover(self, idx: int):
        """Highlight a segment from an external source (e.g. legend row hover)."""
        if idx != self._hover:
            self._hover = idx
            self.update()

    def _seg_at(self, x: float, y: float) -> int:
        if not self.segments:
            return -1
        side = min(self.width(), self.height()) - 8
        cx, cy = self.width() / 2, self.height() / 2
        dx, dy = x - cx, y - cy
        r = math.sqrt(dx * dx + dy * dy)
        outer_r = side / 2
        inner_r = outer_r * 0.60   # hole radius = outer * 0.60
        if r < inner_r or r > outer_r:
            return -1
        angle = (math.degrees(math.atan2(dx, -dy))) % 360
        total = sum(v for v, _ in self.segments) or 1
        cum = 0.0
        for i, (v, _) in enumerate(self.segments):
            cum += v / total * 360
            if angle < cum:
                return i
        return len(self.segments) - 1

    def mouseMoveEvent(self, e):
        idx = self._seg_at(e.position().x(), e.position().y())
        if idx != self._hover:
            self._hover = idx
            self.hovered.emit(idx)
            self.update()

    def leaveEvent(self, e):
        if self._hover != -1:
            self._hover = -1
            self.hovered.emit(-1)
            self.update()

    def paintEvent(self, e):
        if not self.segments:
            p = QPainter(self)
            draw_empty(p, self.rect(), "Nothing to break down")
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._reveal)
        total = sum(v for v, _ in self.segments) or 1
        side = min(self.width(), self.height()) - 8
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2,
                      side, side)
        start = 90 * 16
        p.setPen(Qt.PenStyle.NoPen)
        for i, (v, color) in enumerate(self.segments):
            span = -int(round(v / total * 360 * 16))
            c = QColor(color)
            if i == self._hover:
                c = c.lighter(130)
            p.setBrush(c)
            p.drawPie(rect, start, span)
            start += span
        hole = side * 0.60
        hrect = QRectF((self.width() - hole) / 2, (self.height() - hole) / 2,
                       hole, hole)
        p.setBrush(QColor(self.hole_bg)); p.drawEllipse(hrect)

        if 0 <= self._hover < len(self.segments):
            v, _ = self.segments[self._hover]
            name = self._names[self._hover] if self._hover < len(self._names) else ""
            pct = v / total * 100
            if name:
                f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(10)); p.setFont(f)
                p.setPen(QColor(T.TEXT_MUTED))
                p.drawText(hrect.adjusted(4, hole * 0.12, -4, 0),
                           int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                           name)
            f2 = QFont(T.FONT_FAMILY); f2.setPixelSize(T.scaled(17)); f2.setBold(True); p.setFont(f2)
            p.setPen(QColor(T.TEXT))
            p.drawText(hrect, int(Qt.AlignmentFlag.AlignCenter), f"{pct:.0f}%")
        else:
            if self.center_top:
                f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(17)); f.setBold(True); p.setFont(f)
                p.setPen(QColor(T.TEXT))
                p.drawText(hrect.adjusted(0, hole * 0.18, 0, 0),
                           int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                           self.center_top)
            if self.center_sub:
                f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(10)); p.setFont(f)
                p.setPen(QColor(T.TEXT_MUTED))
                p.drawText(hrect.adjusted(0, 0, 0, -hole * 0.20),
                           int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom),
                           self.center_sub)


class MetricTile(QFrame):
    """Small caption-over-value summary tile.

    Chrome-free, like every other block: the caption/value pair and the gap to
    the next tile are enough to group it. It used to carry a BG_CARD_SOFT fill
    *and* a border, which made it one more equally-weighted box on a page that
    was already nothing but boxes (Filipiuk p35 — figure-ground).
    """
    def __init__(self, caption, value="", color=T.TEXT):
        super().__init__()
        self.setStyleSheet("QFrame{background:transparent; border:none;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(T.SP_XS)
        lay.addWidget(label(caption, T.TEXT_MUTED, T.FS_MICRO))
        self.value = label(value, color, T.FS_METRIC, bold=True)
        lay.addWidget(self.value)
        self._spark: Sparkline | None = None

    def set_value(self, text, color=None):
        self.value.setText(text)
        if color:
            self.value.setStyleSheet(f"color:{color}; background:transparent;")

    def set_spark(self, values, color=None):
        """Show a tiny trend line under the value (added lazily on first call)."""
        if self._spark is None:
            self._spark = Sparkline()
            self.layout().addWidget(self._spark)
        self._spark.set_values(values, color)


class ProgressBar(QWidget):
    """Flat track with a coloured fill (0–1).  Optionally a bullet-style target
    tick and a bounded overrun cap past 100 %.

    The overrun cap is OPT-IN (``overrun=True``) because "past 100 %" is only
    *bad* for a spend-vs-budget bar; for a save-toward-target bar, exceeding
    the target is success and must not be tinted with the loss colour. When
    enabled it is capped at ~15 % of the width so a large overshoot (e.g.
    578 % of target) shows a small red sliver at the end, never floods the
    whole bar over the fill."""
    def __init__(self, frac=0.0, color=T.ACCENT, height=9, target=None,
                 overrun=False):
        super().__init__()
        self._raw = max(0.0, frac)
        self._frac = min(1.0, self._raw)
        self._color = color
        self._target = target          # 0–1 position of a target marker, or None
        self._overrun = overrun
        self.setFixedHeight(height)

    def set_frac(self, frac, color=None, target=None):
        self._raw = max(0.0, frac)
        self._frac = min(1.0, self._raw)
        if color:
            self._color = color
        if target is not None:
            self._target = target
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        h, w = self.height(), self.width()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.BG_PILL))
        p.drawRect(QRectF(0, 0, w, h))
        if self._frac > 0:
            p.setBrush(QColor(self._color))
            p.drawRect(QRectF(0, 0, max(1, w * self._frac), h))
        # overrun cap (opt-in): a small red sliver at the end signalling "over",
        # bounded to ~15 % of the width so a big overshoot never floods the bar.
        if self._overrun and self._raw > 1.0:
            over = min(0.15, self._raw - 1.0)
            oc = QColor(T.RED); oc.setAlpha(200)
            p.setBrush(oc)
            p.drawRect(QRectF(w * (1 - over), 0, w * over, h))
        # target tick — inset 1px from each edge so it stays visible even at
        # target == 1.0 (where it would otherwise sit exactly on the border).
        if self._target is not None and 0 <= self._target <= 1:
            tx = min(w - 1.0, max(1.0, w * self._target))
            p.setPen(QPen(QColor(T.AMBER), 1.6))
            p.drawLine(QPointF(tx, -1), QPointF(tx, h + 1))


class WhoOwesBar(QWidget):
    """Signed horizontal bars per person: green = owed to you, red = you owe."""

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[str, float]] = []     # (name, signed amount)
        self.currency = "$"
        self._hover = -1
        self.setMouseTracking(True)
        self.ROW_H = 26
        self.LABEL_W = 96
        self.VALUE_W = 84

    def set_data(self, rows, currency="$"):
        self.rows = rows
        self.currency = currency
        self._hover = -1
        self.setFixedHeight(max(1, len(rows)) * self.ROW_H + 8)
        self.update()

    def mouseMoveEvent(self, e):
        idx = int((e.position().y() - 4) // self.ROW_H)
        idx = idx if 0 <= idx < len(self.rows) else -1
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, e):
        if self._hover != -1:
            self._hover = -1
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.rows:
            draw_empty(p, self.rect(), "Everyone's settled up")
            return
        maxv = max((abs(v) for _, v in self.rows), default=1.0) or 1.0
        track_x = self.LABEL_W
        track_w = max(20.0, self.width() - self.LABEL_W - self.VALUE_W)
        mid = track_x + track_w / 2
        f = QFont(T.FONT_FAMILY); f.setPixelSize(T.scaled(11))
        fv = QFont(T.FONT_FAMILY); fv.setPixelSize(T.scaled(10)); fv.setBold(True)

        # centre zero line
        p.setPen(QPen(QColor(T.BORDER_LIGHT), 1))
        p.drawLine(QPointF(mid, 4), QPointF(mid, self.height() - 4))

        for i, (name, amt) in enumerate(self.rows):
            y0 = 4 + i * self.ROW_H
            cy = y0 + self.ROW_H / 2
            if i == self._hover:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(T.BG_HOVER))
                p.drawRect(QRectF(0, y0, self.width(), self.ROW_H))
            p.setFont(f); p.setPen(QColor(T.TEXT if i == self._hover else T.TEXT_MUTED))
            p.drawText(QRectF(0, y0, self.LABEL_W - 10, self.ROW_H),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       name if len(name) <= 12 else name[:11] + "…")
            bw = abs(amt) / maxv * (track_w / 2)
            col = T.GREEN if amt >= 0 else T.RED
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(col))
            if amt >= 0:
                p.drawRect(QRectF(mid, cy - 5, bw, 10))
            else:
                p.drawRect(QRectF(mid - bw, cy - 5, bw, 10))
            p.setFont(fv); p.setPen(QColor(col))
            p.drawText(QRectF(self.width() - self.VALUE_W + 4, y0,
                              self.VALUE_W - 6, self.ROW_H),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       money(amt, self.currency, cents=True))


class GoalDialog(QDialog):
    def __init__(self, parent, g, currency):
        super().__init__(parent)
        self.setWindowTitle("Savings goal")
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background:{T.BG_CARD};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(9)

        lay.addWidget(label("Name", T.TEXT_MUTED, 11))
        self.name = QLineEdit(g["name"] if g else "")
        lay.addWidget(self.name)
        lay.addWidget(label("Target amount", T.TEXT_MUTED, 11))
        self.target = MoneySpin()
        self.target.setRange(0, 100_000_000); self.target.setDecimals(0)
        self.target.setPrefix(currency)
        self.target.setValue(g["target"] if g else 1000)
        lay.addWidget(self.target)
        lay.addWidget(label("Saved so far", T.TEXT_MUTED, 11))
        self.saved = MoneySpin()
        self.saved.setRange(0, 100_000_000); self.saved.setDecimals(0)
        self.saved.setPrefix(currency)
        self.saved.setValue(g["saved"] if g else 0)
        lay.addWidget(self.saved)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        bb.setStyleSheet(
            f"QPushButton{{background:{T.BG_INPUT}; border:1px solid {T.BORDER};"
            f"border-radius:{T.RADIUS}px; padding:6px 16px; color:{T.TEXT};}}"
            f"QPushButton:hover{{border-color:{T.BORDER_LIGHT};}}")
        lay.addSpacing(4); lay.addWidget(bb)

    def _apply_to(self, g):
        g["name"] = self.name.text().strip() or "Goal"
        g["target"] = float(self.target.value())
        g["saved"] = float(self.saved.value())

    @staticmethod
    def create(parent, currency):
        dlg = GoalDialog(parent, None, currency)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        g = dm.goal("", 0)
        dlg._apply_to(g)
        return g

    @staticmethod
    def edit(parent, g, currency):
        dlg = GoalDialog(parent, g, currency)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        dlg._apply_to(g)
        return True


# --------------------------------------------------------------------------- #
#  Goals bar — horizontal strip at bottom of OverviewPage
# --------------------------------------------------------------------------- #
class GoalsBar(QFrame):
    """Full-width horizontal goals strip shown across the bottom of the overview."""

    def __init__(self, manager):
        super().__init__()
        self.dm = manager
        self.setObjectName("GoalsBar")
        self.setStyleSheet(
            f"#GoalsBar{{background:transparent; border:none;}}")
        self.setFixedHeight(120)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 10, 16, 10)
        outer.setSpacing(14)

        hdr = label("GOALS", T.TEXT_MUTED, 9, bold=True)
        hdr.setFixedWidth(38)
        outer.addWidget(hdr, 0, Qt.AlignmentFlag.AlignTop)

        sep = QFrame(); sep.setFixedWidth(1)
        sep.setStyleSheet(f"background:{T.BORDER_SOFT}; border:none;")
        outer.addWidget(sep)

        self._holder = QWidget()
        self._holder.setStyleSheet("background:transparent;")
        self._hlay = QHBoxLayout(self._holder)
        self._hlay.setSpacing(24)
        self._hlay.setContentsMargins(0, 0, 0, 0)

        self._scroll = BoundedScroll()
        self._scroll.setWidget(self._holder)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background:transparent; border:none;")
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(self._scroll, 1)

    def refresh(self, currency="$"):
        clear_layout(self._hlay)
        goals = self.dm.load_goals().get("goals", [])
        if not goals:
            self._hlay.addWidget(label("No goals — add from Goals page", T.TEXT_DIM, 11))
            self._hlay.addStretch(1)
            return
        for g in goals:
            target = float(g.get("target", 0))
            saved  = float(g.get("saved", 0))
            frac   = min(1.0, saved / target) if target > 0 else 0.0
            left   = max(0.0, target - saved)
            done   = frac >= 1.0

            chip = QWidget()
            chip.setStyleSheet("background:transparent;")
            chip.setFixedWidth(188)
            vlay = QVBoxLayout(chip)
            vlay.setContentsMargins(0, 0, 0, 0)
            vlay.setSpacing(6)

            # name + percentage on same row
            top_row = QHBoxLayout(); top_row.setSpacing(4)
            name_lbl = label(g["name"], T.TEXT if done else T.TEXT_MUTED, 12, bold=True)
            name_lbl.setWordWrap(False)
            pct_col  = T.GREEN if done else T.ACCENT
            top_row.addWidget(name_lbl, 1)
            top_row.addWidget(label(f"{frac * 100:.0f}%", pct_col, 11, bold=done))
            vlay.addLayout(top_row)

            vlay.addWidget(ProgressBar(frac, T.GREEN if done else T.SERIES[1], 7))

            # saved / target row
            mid_row = QHBoxLayout(); mid_row.setSpacing(4)
            mid_row.addWidget(label(money(saved, currency, signed=False), T.TEXT, 11))
            mid_row.addWidget(label("/", T.TEXT_DIM, 10))
            mid_row.addWidget(label(money(target, currency, signed=False), T.TEXT_DIM, 10))
            mid_row.addStretch(1)
            vlay.addLayout(mid_row)

            # remaining row
            if done:
                vlay.addWidget(label("Goal reached!", T.GREEN, 10))
            else:
                rem_row = QHBoxLayout(); rem_row.setSpacing(4)
                rem_row.addWidget(label(money(left, currency, signed=False), T.RED, 11, bold=True))
                rem_row.addWidget(label("left", T.TEXT_DIM, 10))
                rem_row.addStretch(1)
                vlay.addLayout(rem_row)

            self._hlay.addWidget(chip)
        self._hlay.addStretch(1)

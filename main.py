"""Personal budgeting desktop app (PyQt6).

Run normally::

    python main.py

Render a head-less PNG of a page (used while iterating on the design)::

    python main.py --shot preview.png [--page analytics]
"""

from __future__ import annotations

import os
import sys
from datetime import date

from PyQt6.QtCore import Qt, QDate, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDoubleSpinBox,
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QVBoxLayout,
    QWidget,
)

import backend as B
import datamanagement as dm
import exporters as X
import importers as IMP
import theme as T
from widgets import (
    AreaChart, BoundedScroll, CalendarHeatmap, ChartCard, ChartLegend,
    Clickable, DonutChart, FanChart, GoalDialog, GoalsBar, GroupedBarChart,
    LedgerCard, LineChart, MetricTile, PersonDialog, PredictedIncomeCard,
    ProgressBar, SankeyChart, SegTabBar, SharedPlanDialog, Sidebar, StackedBarChart,
    SubscriptionTimeline, SummaryCard, TopBar, WhoOwesBar, clear_layout, hsep,
    label, money, repeat_label, retain_size, tag_chip,
)


# --------------------------------------------------------------------------- #
#  Shared helpers
# --------------------------------------------------------------------------- #
def card(margins=(18, 16, 18, 16), spacing=10):
    fr = QFrame(); fr.setObjectName("Card")
    fr.setStyleSheet(
        f"#Card{{background:{T.BG_CARD}; border:1px solid {T.BORDER_SOFT};"
        f"border-radius:{T.RADIUS}px;}}")
    lay = QVBoxLayout(fr); lay.setContentsMargins(*margins); lay.setSpacing(spacing)
    return fr, lay


def scrollable(inner):
    sc = BoundedScroll(); sc.setWidgetResizable(True)
    sc.setStyleSheet("background:transparent;border:none;")
    sc.setWidget(inner)
    return sc



def chip(color, size=10):
    c = QFrame(); c.setFixedSize(size, size)
    c.setStyleSheet(f"background:{color};")
    return c


def tile_row(captions):
    """Build an evenly-spaced row of MetricTiles; returns (layout, [tiles])."""
    row = QHBoxLayout(); row.setSpacing(12)
    tiles = []
    for cap in captions:
        t = MetricTile(cap)
        tiles.append(t); row.addWidget(t, 1)
    return row, tiles


# --------------------------------------------------------------------------- #
#  Overview (the dashboard from the mock-up)
# --------------------------------------------------------------------------- #
class OverviewPage(QWidget):
    def __init__(self, manager, doc, year, month, today, on_change):
        super().__init__()
        self.dm, self.doc = manager, doc
        self.year, self.month, self.today = year, month, today

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(T.GAP)

        main_row = QHBoxLayout()
        main_row.setSpacing(T.GAP)
        main_row.setContentsMargins(0, 0, 0, 0)

        self.income_card = LedgerCard("income", doc, today, doc.get("currency", "$"))
        self.expense_card = LedgerCard("expense", doc, today, doc.get("currency", "$"))
        self.income_card.store = manager      # edits persist to the flat store
        self.expense_card.store = manager
        self.income_card.changed.connect(on_change)
        self.expense_card.changed.connect(on_change)
        for c in (self.income_card, self.expense_card):
            c.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        right = QWidget(); right.setFixedWidth(356)
        right.setStyleSheet("background:transparent;")
        rlay = QVBoxLayout(right); rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(T.GAP)
        self.summary = SummaryCard(manager, doc, year, month, today)
        self.chart = ChartCard(manager, year, month, doc.get("target_pnl", 0))
        self.chart.setMinimumHeight(196)
        self.predicted = PredictedIncomeCard(doc, year, month, store=manager)
        self.budget_card, bly = card(margins=(16, 14, 16, 14), spacing=8)
        bly.addWidget(label("Budget vs actual — top 5", T.TEXT_MUTED, 11))
        self.budget_mini = GroupedBarChart()
        bly.addWidget(self.budget_mini)
        retain_size(self.budget_card)   # hiding it (no budget data) mustn't
                                        # shove chart/predicted below it
        rlay.addWidget(self.summary)
        rlay.addWidget(self.chart, 1)   # the one card that grows/shrinks with
                                        # the window, mirroring the ledger
                                        # lists on the left (see _equalize_lists)
        rlay.addWidget(self.predicted)
        rlay.addWidget(self.budget_card)
        self._refresh_budget_mini()

        main_row.addWidget(self.income_card, 1, Qt.AlignmentFlag.AlignTop)
        main_row.addWidget(self.expense_card, 1, Qt.AlignmentFlag.AlignTop)
        main_row.addWidget(right)

        self.goals_bar = GoalsBar(manager)
        self.goals_bar.refresh(doc.get("currency", "$"))

        outer.addLayout(main_row, 1)
        outer.addWidget(self.goals_bar)
        QTimer.singleShot(0, self._equalize_lists)

    def _refresh_budget_mini(self):
        """Top-5 budgeted categories, bullet-bar style, on the right rail."""
        rep = B.budget_report(self.dm.items(), self.dm.transactions(),
                              self.year, self.month)
        rows = sorted(
            [(r["name"], r["ideal"], r["actual"]) for r in rep["rows"]
             if r["ideal"] or r["actual"]],
            key=lambda r: -max(r[1], r[2]))[:5]
        self.budget_card.setVisible(bool(rows))
        self.budget_mini.set_data(rows, self.doc.get("currency", "$"))

    def _equalize_lists(self):
        """Make both ledger borders end at the same place — the shorter list
        stretches down to match the longer one's content height."""
        h = max(self.income_card.list_hint(), self.expense_card.list_hint(), 60)
        goals_h = self.goals_bar.height() + T.GAP
        avail = self.height() - 34 - goals_h   # page margins + goals bar
        if avail > 220:                         # keep on-screen; the card scrolls if huge
            h = min(h, avail - 108)             # ≈ header + tabs + divider block
        self.income_card.set_list_height(h)
        self.expense_card.set_list_height(h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._equalize_lists()

    def set_month(self, doc, year, month):
        self.doc, self.year, self.month = doc, year, month
        self.income_card.set_doc(doc)
        self.expense_card.set_doc(doc)
        self.summary.set_context(doc, year, month)
        self.chart.set_context(year, month, doc.get("target_pnl", 0),
                               doc.get("currency", "$"))
        self.predicted.set_context(doc, year, month)
        self.goals_bar.refresh(doc.get("currency", "$"))
        self._refresh_budget_mini()
        QTimer.singleShot(0, self._equalize_lists)   # after layout settles

    def set_range(self, range_doc, year, month):
        """ISO-week / sub-month lens: ledgers + headline reflect the range;
        chart, predicted and goals stay anchored to the month for context."""
        self.doc, self.year, self.month = range_doc, year, month
        self.income_card.set_doc(range_doc)
        self.expense_card.set_doc(range_doc)
        self.summary.set_range(range_doc, year, month)
        self.chart.set_context(year, month, range_doc.get("target_pnl", 0),
                               range_doc.get("currency", "$"))
        self.predicted.set_context(range_doc, year, month)
        self.goals_bar.refresh(range_doc.get("currency", "$"))
        self._refresh_budget_mini()
        QTimer.singleShot(0, self._equalize_lists)

    def refresh(self):
        self.income_card.rebuild()
        self.expense_card.rebuild()
        self.summary.refresh()
        self.chart.set_context(self.year, self.month, self.doc.get("target_pnl", 0),
                               self.doc.get("currency", "$"))
        self.predicted.set_context(self.doc, self.year, self.month)
        self.goals_bar.refresh(self.doc.get("currency", "$"))
        self._refresh_budget_mini()
        QTimer.singleShot(0, self._equalize_lists)

    def set_summary_period(self, period):
        self.summary.set_period(period)

    def set_week(self, week_of_month: int | None):
        self.summary.set_week(week_of_month)
        self.income_card.set_week_mode(week_of_month)
        self.expense_card.set_week_mode(week_of_month)


# --------------------------------------------------------------------------- #
#  Income / Expenses detail pages — tiles + breakdown + trend + editable ledger
# --------------------------------------------------------------------------- #
class LedgerDetailPage(QWidget):
    def __init__(self, kind, manager, doc, year, month, on_change):
        super().__init__()
        self.kind, self.dm, self.on_change = kind, manager, on_change
        self.income = kind == "income"
        self.doc, self.year, self.month = doc, year, month

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 18); lay.setSpacing(14)

        caps = (["This month", "Sources", "Recurring", "One-off"] if self.income
                else ["This month", "Categories", "Recurring", "% of income"])
        trow, self.tiles = tile_row(caps)
        lay.addLayout(trow)

        cols = QHBoxLayout(); cols.setSpacing(T.GAP)
        self.donut_card, dlay = card()
        self.donut_title = label("", T.TEXT_MUTED, 12)
        dlay.addWidget(self.donut_title)
        drow = QHBoxLayout(); drow.setSpacing(14)
        self.donut = DonutChart(); self.donut.setFixedSize(168, 168)
        drow.addWidget(self.donut)
        self.legend = QVBoxLayout(); self.legend.setSpacing(7)
        host = QVBoxLayout(); host.addStretch(1); host.addLayout(self.legend); host.addStretch(1)
        drow.addLayout(host, 1)
        dlay.addLayout(drow)
        cols.addWidget(self.donut_card, 1)

        self.trend_card, tlay = card()
        self.trend_title = label("", T.TEXT_MUTED, 12)
        tlay.addWidget(self.trend_title)
        self.trend = LineChart(); self.trend.setMinimumHeight(184)
        tlay.addWidget(self.trend)
        cols.addWidget(self.trend_card, 1)
        lay.addLayout(cols)

        self.card = LedgerCard(kind, doc, date.today(), doc.get("currency", "$"))
        self.card.changed.connect(self._changed)
        lay.addWidget(self.card)

        outer.addWidget(scrollable(content))
        self._refresh_summary()

    def _changed(self):
        self.on_change()
        self._refresh_summary()

    def set_context(self, doc, year, month):
        self.doc, self.year, self.month = doc, year, month
        self.card.set_doc(doc)
        self._refresh_summary()

    def _series(self):
        out = []
        for back in range(4, -1, -1):
            idx = self.year * 12 + (self.month - 1) - back
            y, m = idx // 12, idx % 12 + 1
            val = 0.0
            if self.dm.has_month(y, m):
                d = self.dm.load_month(y, m)
                val = B.income_total(d) if self.income else B.expense_total(d)
            out.append((dm.MONTH_ABBR[m], val))
        return out

    def _refresh_summary(self):
        doc, y, m = self.doc, self.year, self.month
        cur = doc.get("currency", "$")
        items = doc.get("income" if self.income else "expenses", [])
        sign = T.GREEN if self.income else T.RED
        total = B.active_total(items, y, m)
        rec = B.recurring_total(items, y, m)

        self.tiles[0].set_value(money(total if self.income else -total, cur), sign)
        self.tiles[1].set_value(str(len(items)))
        self.tiles[2].set_value(money(rec if self.income else -rec, cur), sign)
        if self.income:
            self.tiles[3].set_value(money(total - rec, cur), T.TEXT_MUTED)
        else:
            inc = B.income_total(doc)
            pct = (total / inc * 100) if inc else 0
            self.tiles[3].set_value(f"{pct:.0f}%", T.RED if pct > 100 else T.TEXT)

        mn = dm.MONTH_NAMES[m]
        self.donut_title.setText(f"Breakdown — {mn}")
        data = [(n, B.active_amount(n, y, m)) for n in items]
        data = sorted([t for t in data if t[1] > 0], key=lambda t: t[1], reverse=True)
        dtotal = sum(a for _, a in data) or 1
        segs = [(a, T.SERIES[i % len(T.SERIES)]) for i, (_, a) in enumerate(data)]
        names = [n["name"] for n, _ in data]
        self.donut.set_segments(segs, money(dtotal, cur, signed=False),
                                "income" if self.income else "spent", names=names)
        clear_layout(self.legend)
        for i, (n, a) in enumerate(data):
            row = _LegendRow(self.donut, i, T.SERIES[i % len(T.SERIES)],
                             n["name"], f"{a / dtotal * 100:.0f}%",
                             money(a if self.income else -a, cur))
            self.legend.addWidget(row)

        self.trend_title.setText(("Income" if self.income else "Expenses")
                                 + " — last 5 months")
        self.trend.set_series(self._series(), fill=True, currency=cur,
                              color=(T.GREEN if self.income else T.RED))


# --------------------------------------------------------------------------- #
#  Hoverable legend row — syncs highlight with a DonutChart
# --------------------------------------------------------------------------- #
class _LegendRow(QWidget):
    def __init__(self, donut, idx, color, name, pct_str, amount_str):
        super().__init__()
        self._donut = donut
        self._idx = idx
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3); lay.setSpacing(8)
        chip = QFrame(); chip.setFixedSize(10, 10)
        chip.setStyleSheet(f"background:{color}; border:none;")
        lay.addWidget(chip)
        lay.addWidget(label(name, T.TEXT, 12))
        lay.addStretch(1)
        lay.addWidget(label(pct_str, T.TEXT_MUTED, 11))
        lay.addSpacing(6)
        lay.addWidget(label(amount_str, T.TEXT, 12, bold=True))
        self.setStyleSheet("background:transparent;")

    def enterEvent(self, e):
        self._donut.set_hover(self._idx)
        self.setStyleSheet(f"background:{T.BG_HOVER};")

    def leaveEvent(self, e):
        self._donut.set_hover(-1)
        self.setStyleSheet("background:transparent;")


# --------------------------------------------------------------------------- #
#  Analytics – Overview tab (averages, P&L trend, expense donut, income bars)
# --------------------------------------------------------------------------- #
class _AnalyticsOverview(QWidget):
    navigate_to = pyqtSignal(int, int)

    def __init__(self, manager, doc, year, month):
        super().__init__()
        self.dm = manager
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 18); lay.setSpacing(14)

        trow, self.tiles = tile_row(
            ["Avg income / mo", "Avg expenses / mo", "Avg P&L / mo", "Avg savings"])
        lay.addLayout(trow)

        trow2, self.tiles2 = tile_row(["Best month", "Worst month", "Months positive", "Income growth"])
        lay.addLayout(trow2)

        bva_card, bvly = card()
        self._bva_title = label("Budget vs actual — this month", T.TEXT_MUTED, 12)
        bvly.addWidget(self._bva_title)
        self.bva = GroupedBarChart()
        bvly.addWidget(self.bva)
        lay.addWidget(bva_card)

        stk_card, sly = card()
        sly.addWidget(label("Spending composition — last 6 months", T.TEXT_MUTED, 12))
        srow = QHBoxLayout(); srow.setSpacing(14)
        self.stacked = StackedBarChart()
        self.stacked.setMinimumHeight(230)
        srow.addWidget(self.stacked, 1)
        self.stacked_legend = ChartLegend()
        leg_host = QVBoxLayout(); leg_host.addStretch(1)
        leg_host.addWidget(self.stacked_legend); leg_host.addStretch(1)
        srow.addLayout(leg_host)
        sly.addLayout(srow)
        self.stacked.hovered.connect(
            lambda m, c: self.stacked_legend.set_hover(c))
        self.stacked_legend.hovered.connect(self.stacked.set_hover_cat)
        lay.addWidget(stk_card)

        flow_card, fcly = card()
        self._flow_title = label("Cash flow — this month", T.TEXT_MUTED, 12)
        fcly.addWidget(self._flow_title)
        self.sankey = SankeyChart()
        fcly.addWidget(self.sankey)
        lay.addWidget(flow_card)

        fan_card, fanly = card()
        fanly.addWidget(label("Liquid-balance forecast — next 6 months",
                              T.TEXT_MUTED, 12))
        self.fan = FanChart()
        fanly.addWidget(self.fan)
        lay.addWidget(fan_card)

        nw_card, nwly = card()
        self._nw_title = label("Net worth — history", T.TEXT_MUTED, 12)
        nwly.addWidget(self._nw_title)
        self.area = AreaChart()
        nwly.addWidget(self.area)
        lay.addWidget(nw_card)

        self._trend_label = label("P&L vs target — last 5 months  ·  click a point to filter breakdown",
                                  T.TEXT_MUTED, 12)
        trend, tlay = card()
        tlay.addWidget(self._trend_label)
        self.trend = LineChart(); self.trend.setMinimumHeight(210)
        self.trend.clicked_idx.connect(self._on_trend_click)
        tlay.addWidget(self.trend)
        lay.addWidget(trend)

        inc_exp_card, iely = card()
        iely.addWidget(label("Income vs Expenses — all months", T.TEXT_MUTED, 12))
        self.inc_exp_chart = LineChart()
        self.inc_exp_chart.setMinimumHeight(180)
        iely.addWidget(self.inc_exp_chart)
        lay.addWidget(inc_exp_card)

        pred_card, pely = card()
        pely.addWidget(label("Predicted Income — next 6 months (recurring sources)",
                             T.TEXT_MUTED, 12))
        self.pred_chart = LineChart()
        self.pred_chart.setMinimumHeight(160)
        pely.addWidget(self.pred_chart)
        pely.addSpacing(8); pely.addWidget(hsep()); pely.addSpacing(8)
        pely.addWidget(label("Recurring sources — next month", T.TEXT_DIM, 10, bold=True))
        self.pred_breakdown_box = QVBoxLayout(); self.pred_breakdown_box.setSpacing(5)
        pely.addLayout(self.pred_breakdown_box)
        lay.addWidget(pred_card)

        tag_card, tly = card()
        tly.addWidget(label("Spending by tag — this month", T.TEXT_MUTED, 12))
        self.tag_box = QVBoxLayout(); self.tag_box.setSpacing(5)
        tly.addLayout(self.tag_box)
        lay.addWidget(tag_card)

        rec_card, rcly = card()
        rcly.addWidget(label("Plan vs actual — this month", T.TEXT_MUTED, 12))
        self.rec_box = QVBoxLayout(); self.rec_box.setSpacing(5)
        rcly.addLayout(self.rec_box)
        lay.addWidget(rec_card)

        cols = QHBoxLayout(); cols.setSpacing(T.GAP)

        self.donut_card, dlay = card()
        self.donut_title = label("", T.TEXT_MUTED, 12)
        dlay.addWidget(self.donut_title)
        drow = QHBoxLayout(); drow.setSpacing(14)
        self.donut = DonutChart(); self.donut.setFixedSize(168, 168)
        drow.addWidget(self.donut)
        self.legend = QVBoxLayout(); self.legend.setSpacing(2)
        leg_host = QVBoxLayout(); leg_host.addStretch(1)
        leg_host.addLayout(self.legend); leg_host.addStretch(1)
        drow.addLayout(leg_host, 1)
        dlay.addLayout(drow)
        cols.addWidget(self.donut_card, 1)

        self.inc_card, ilay = card()
        self.inc_title = label("", T.TEXT_MUTED, 12)
        ilay.addWidget(self.inc_title)
        self.inc_box = QVBoxLayout(); self.inc_box.setSpacing(12)
        ilay.addLayout(self.inc_box); ilay.addStretch(1)
        cols.addWidget(self.inc_card, 1)

        lay.addLayout(cols)

        cmp_card, clay = card()
        hdr = QHBoxLayout()
        for cap, w in [("Month", 90), ("Income", 80), ("Expenses", 80), ("P&L", 70), ("Rate", 50)]:
            lbl = label(cap, T.TEXT_DIM, 10, bold=True)
            if w > 0:
                lbl.setFixedWidth(w)
            hdr.addWidget(lbl)
        hdr.addStretch(1)
        clay.addLayout(hdr)
        self._cmp_box = QVBoxLayout(); self._cmp_box.setSpacing(3)
        clay.addLayout(self._cmp_box)
        lay.addWidget(cmp_card)

        lay.addStretch(1)
        outer.addWidget(scrollable(content))
        self._months_series: list[tuple[int, int]] = []

    def set_context(self, doc, year, month):
        self.doc = doc
        cur = doc.get("currency", "$")

        incs, exps, pnls, rates = [], [], [], []
        for y, m in self.dm.list_months():
            d = self.dm.load_month(y, m)
            inc = B.income_total(d)
            exp = B.expense_total(d)
            p = inc - exp
            incs.append(inc); exps.append(exp)
            pnls.append(p)
            rates.append((p / inc) if inc else 0.0)

        def avg(xs): return sum(xs) / len(xs) if xs else 0
        self.tiles[0].set_value(money(avg(incs), cur), T.GREEN)
        self.tiles[1].set_value(money(-avg(exps), cur), T.RED)
        self.tiles[2].set_value(money(avg(pnls), cur),
                                T.GREEN if avg(pnls) >= 0 else T.RED)
        self.tiles[3].set_value(f"{avg(rates) * 100:.1f}%", T.ACCENT)

        # tiny trend lines under the averages
        if len(incs) >= 2:
            self.tiles[0].set_spark(incs[-12:], T.GREEN)
            self.tiles[1].set_spark(exps[-12:], T.RED)
            self.tiles[2].set_spark(pnls[-12:],
                                    T.GREEN if pnls[-1] >= 0 else T.RED)
            self.tiles[3].set_spark(rates[-12:], T.ACCENT)

        # budget vs actual bullet rows (biggest first)
        mn_name = dm.MONTH_NAMES[month]
        self._bva_title.setText(f"Budget vs actual — {mn_name}")
        rep_bva = B.budget_report(self.dm.items(), self.dm.transactions(),
                                  year, month)
        bva_rows = sorted(
            [(r["name"], r["ideal"], r["actual"]) for r in rep_bva["rows"]
             if r["ideal"] or r["actual"]],
            key=lambda r: -max(r[1], r[2]))
        self.bva.set_data(bva_rows, cur)

        # spending composition — stacked bars + synced legend
        cs = B.category_series(self.dm.items(), year, month, count=6)
        colors = [T.SERIES[i % len(T.SERIES)]
                  for i in range(len(cs["categories"]))]
        self.stacked.set_data(cs["labels"], cs["categories"], cs["matrix"],
                              colors, cur)
        self.stacked_legend.set_rows(
            [(colors[i], name,
              money(sum(row[i] for row in cs["matrix"]), cur, signed=False))
             for i, name in enumerate(cs["categories"])])

        # cash-flow sankey — this month
        self._flow_title.setText(f"Cash flow — {mn_name}")
        flow = B.cashflow_links(self.dm.items(), year, month)
        self.sankey.set_data(flow["income"], flow["outflows"], cur)

        # liquid-balance forecast band
        accounts = self.dm.accounts()
        start_bal = B.liquid_balance(accounts)
        band = B.forecast_band(self.dm.items(), start_bal, date.today(), months=6)
        hist = [("Now", start_bal)]
        self.fan.set_data(hist, band, cur)

        # net-worth area (real snapshots once ≥2 exist, else reconstructed)
        nw = B.net_worth(accounts)
        self._nw_title.setText(
            f"Net worth — {money(nw['net'], cur, signed=False)}")
        nw_series = B.net_worth_series(self.dm.items(), accounts, date.today(),
                                       self.dm.networth_history(), months=6)
        self.area.set_data(nw_series, cur)

        # second row tiles
        if pnls:
            best_idx = pnls.index(max(pnls))
            worst_idx = pnls.index(min(pnls))
            months_list = self.dm.list_months()
            best_ym = months_list[best_idx] if best_idx < len(months_list) else (year, month)
            worst_ym = months_list[worst_idx] if worst_idx < len(months_list) else (year, month)
            self.tiles2[0].set_value(
                f"{dm.MONTH_ABBR[best_ym[1]]} {best_ym[0]}\n{money(max(pnls), cur)}",
                T.GREEN)
            self.tiles2[1].set_value(
                f"{dm.MONTH_ABBR[worst_ym[1]]} {worst_ym[0]}\n{money(min(pnls), cur)}",
                T.RED)
            positive = sum(1 for p in pnls if p > 0)
            self.tiles2[2].set_value(f"{positive}/{len(pnls)}", T.ACCENT)
            # income growth: this month vs 3-month avg of prior months
            if len(incs) >= 2:
                prior_avg = sum(incs[:-1][-3:]) / len(incs[:-1][-3:])
                growth = ((incs[-1] - prior_avg) / prior_avg * 100) if prior_avg else 0
                arrow = "↑" if growth >= 0 else "↓"
                gcol = T.GREEN if growth >= 0 else T.RED
                self.tiles2[3].set_value(f"{arrow}{abs(growth):.1f}%", gcol)
            else:
                self.tiles2[3].set_value("—", T.TEXT_DIM)
        else:
            for t in self.tiles2:
                t.set_value("—", T.TEXT_DIM)

        # Build 5-month series and store for click navigation
        hist = B.history(self.dm, year, month, 5)
        self._months_series = []
        for back in range(4, -1, -1):
            idx2 = year * 12 + (month - 1) - back
            y2, m2 = idx2 // 12, idx2 % 12 + 1
            self._months_series.append((y2, m2))
        self.trend.set_series([(lab, v) for lab, v, _ in hist],
                              target=doc.get("target_pnl"), fill=True, currency=cur)
        self.trend.set_selected(4)   # highlight current month

        # income vs expenses dual-line chart (use secondary series)
        all_months = self.dm.list_months()
        inc_series = [(f"{dm.MONTH_ABBR[m]}\n{y}", B.income_total(self.dm.load_month(y, m)))
                      for y, m in all_months]
        exp_series = [(f"{dm.MONTH_ABBR[m]}\n{y}", B.expense_total(self.dm.load_month(y, m)))
                      for y, m in all_months]
        self.inc_exp_chart.set_series(inc_series, fill=False, currency=cur,
                                       color=T.GREEN, highlight_last=True)
        self.inc_exp_chart.set_secondary_series(exp_series, color=T.RED)

        # predicted income — next 6 months (the store projects recurrence forward)
        pred_series = []
        for i in range(1, 7):
            fi = year * 12 + (month - 1) + i
            fy, fm = fi // 12, fi % 12 + 1
            pred_series.append((dm.MONTH_ABBR[fm], B.income_total(self.dm.load_month(fy, fm))))
        self.pred_chart.set_series(
            pred_series, fill=True, currency=cur, color=T.ACCENT, highlight_last=False)

        clear_layout(self.pred_breakdown_box)
        next_idx = year * 12 + (month - 1) + 1
        ny, nm = next_idx // 12, next_idx % 12 + 1
        breakdown = [(n, a) for n, a in
                     B.leaf_breakdown(self.dm.load_month(ny, nm), "income") if a]
        if not breakdown:
            self.pred_breakdown_box.addWidget(
                label("No income sources next month", T.TEXT_DIM, 11))
        else:
            for name, amt in breakdown:
                r = QHBoxLayout(); r.setSpacing(8)
                r.addWidget(label(name, T.TEXT_MUTED, 11))
                r.addStretch(1)
                r.addWidget(label(money(amt, cur, signed=False), T.GREEN, 11, bold=True))
                self.pred_breakdown_box.addLayout(r)

        # spending by tag (this month)
        clear_layout(self.tag_box)
        import calendar as _cal
        last = _cal.monthrange(year, month)[1]
        tags = B.spend_by_tag(self.dm.items(), date(year, month, 1),
                              date(year, month, last))
        if not tags:
            self.tag_box.addWidget(label("No expenses tagged yet — add tags on the "
                                         "Overview (hover a row, click #).", T.TEXT_DIM, 11))
        else:
            tmax = max(a for _, a in tags) or 1.0
            for tname, amt in tags:
                r = QHBoxLayout(); r.setSpacing(8)
                r.addWidget(label(tname, T.TEXT_MUTED, 11))
                bar = ProgressBar(amt / tmax, T.ACCENT, 6); bar.setFixedWidth(120)
                r.addWidget(bar)
                r.addStretch(1)
                r.addWidget(label(money(amt, cur, signed=False), T.RED, 11, bold=True))
                self.tag_box.addLayout(r)

        # plan vs actual (reconcile imported transactions against the plan)
        clear_layout(self.rec_box)
        rep = B.budget_report(self.dm.items(), self.dm.transactions(), year, month)
        if not rep["has_txn"]:
            self.rec_box.addWidget(label(
                "Import a bank file (Settings → Connect bank accounts) to reconcile "
                "your plan against actual spend.", T.TEXT_DIM, 11))
        else:
            for r in rep["rows"]:
                diff = r["planned"] - r["actual"]      # +ve = under plan
                row = QHBoxLayout(); row.setSpacing(8)
                row.addWidget(label(r["name"], T.TEXT_MUTED, 11))
                row.addStretch(1)
                row.addWidget(label(f"plan {money(r['planned'], cur, signed=False)}",
                                    T.TEXT_DIM, 11))
                row.addWidget(label(f"actual {money(r['actual'], cur, signed=False)}",
                                    T.TEXT, 11, bold=True))
                row.addWidget(label(
                    f"{money(abs(diff), cur, signed=False)} {'under' if diff >= 0 else 'over'}",
                    T.GREEN if diff >= 0 else T.RED, 11))
                self.rec_box.addLayout(row)

        # month comparison table
        clear_layout(self._cmp_box)
        for (y, m), inc, exp, pnl_v, rate in reversed(list(zip(
                self.dm.list_months(), incs, exps, pnls, rates))):
            row = QHBoxLayout(); row.setSpacing(0)
            mn_lbl = Clickable(f"{dm.MONTH_ABBR[m]} {y}", T.TEXT_MUTED, 11)
            mn_lbl.setFixedWidth(90)
            mn_lbl.clicked.connect(
                lambda _=False, yy=y, mm=m: self._on_month_click(yy, mm))
            row.addWidget(mn_lbl)
            inc_lbl = label(money(inc, cur), T.GREEN, 11); inc_lbl.setFixedWidth(80)
            row.addWidget(inc_lbl)
            exp_lbl = label(money(-exp, cur), T.RED, 11); exp_lbl.setFixedWidth(80)
            row.addWidget(exp_lbl)
            pcol = T.GREEN if pnl_v >= 0 else T.RED
            pnl_lbl = label(money(pnl_v, cur), pcol, 11, bold=True); pnl_lbl.setFixedWidth(70)
            row.addWidget(pnl_lbl)
            rate_lbl = label(f"{rate*100:.1f}%", T.ACCENT, 11); rate_lbl.setFixedWidth(50)
            row.addWidget(rate_lbl)
            row.addStretch(1)
            self._cmp_box.addLayout(row)

        self._show_breakdown(doc, year, month)

    def _on_trend_click(self, idx: int):
        if not (0 <= idx < len(self._months_series)):
            return
        y, m = self._months_series[idx]
        self.trend.set_selected(idx)
        d = self.dm.load_month(y, m) if self.dm.has_month(y, m) else self.doc
        self._show_breakdown(d, y, m)

    def _on_month_click(self, year: int, month: int):
        # find the index in _months_series
        for i, (y, m) in enumerate(self._months_series):
            if y == year and m == month:
                self.trend.set_selected(i)
                break
        d = self.dm.load_month(year, month) if self.dm.has_month(year, month) else self.doc
        self._show_breakdown(d, year, month)

    def _show_breakdown(self, doc, year, month):
        cur = doc.get("currency", "$")
        mn = dm.MONTH_NAMES[month]

        self.donut_title.setText(f"Expense breakdown — {mn}")
        # Store selected month for navigation
        self._sel_year, self._sel_month = year, month
        exp = [(n, B.active_amount(n, year, month)) for n in doc.get("expenses", [])]
        exp = sorted([t for t in exp if t[1] > 0], key=lambda t: t[1], reverse=True)
        total = sum(a for _, a in exp) or 1
        segs = [(a, T.SERIES[i % len(T.SERIES)]) for i, (_, a) in enumerate(exp)]
        names = [n["name"] for n, _ in exp]
        self.donut.set_segments(segs, money(total, cur, signed=False), "spent", names=names)
        clear_layout(self.legend)
        for i, (n, a) in enumerate(exp):
            row = _LegendRow(self.donut, i, T.SERIES[i % len(T.SERIES)],
                             n["name"], f"{a / total * 100:.0f}%",
                             money(-a, cur))
            self.legend.addWidget(row)

        self.inc_title.setText(f"Income sources — {mn}")
        clear_layout(self.inc_box)
        inc = [(n, B.active_amount(n, year, month)) for n in doc.get("income", [])]
        inc = sorted([t for t in inc if t[1] > 0], key=lambda t: t[1], reverse=True)
        mx = max((a for _, a in inc), default=1) or 1
        for n, a in inc:
            box = QVBoxLayout(); box.setSpacing(5)
            head = QHBoxLayout()
            head.addWidget(label(n["name"], T.TEXT, 12)); head.addStretch(1)
            head.addWidget(label(money(a, cur), T.GREEN, 12, bold=True))
            box.addLayout(head)
            box.addWidget(ProgressBar(a / mx, T.GREEN))
            self.inc_box.addLayout(box)

        # navigation link
        if not hasattr(self, '_nav_link'):
            self._nav_link = Clickable("", T.TEXT_DIM, 11, hover=T.ACCENT)
            self._nav_link.clicked.connect(
                lambda _=False: self.navigate_to.emit(self._sel_year, self._sel_month))
            self.inc_card.layout().addWidget(self._nav_link)
        self._nav_link.setText(f"→ View {dm.MONTH_ABBR[month]} {year} in Overview")


# --------------------------------------------------------------------------- #
#  Goals – monthly target progress + named savings goals
# --------------------------------------------------------------------------- #
def _spin(lo, hi, decimals=True):
    sp = QDoubleSpinBox() if decimals else QSpinBox()
    sp.setRange(lo, hi)
    if decimals:
        sp.setDecimals(0); sp.setPrefix("$")
    sp.setFixedWidth(130)
    return sp


def _button(text, fg, bg, border):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{bg}; color:{fg}; border:1px solid {border};"
        f"border-radius:0px; padding:8px 16px;}}"
        f"QPushButton:hover{{border-color:{fg};}}")
    return b


# --------------------------------------------------------------------------- #
#  Analytics page — tabbed: Overview | Income | Expenses
# --------------------------------------------------------------------------- #
class AnalyticsPage(QWidget):
    def __init__(self, manager, doc, year, month, on_change):
        super().__init__()
        self._on_change = on_change

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        tabhost = QWidget()
        tabhost.setStyleSheet(
            f"background:{T.BG_CARD}; border-bottom:1px solid {T.BORDER_SOFT};")
        tlay = QHBoxLayout(tabhost)
        tlay.setContentsMargins(20, 0, 20, 0)
        self._tabbar = SegTabBar(["Overview", "Income", "Expenses"], 0, kind="tab")
        self._tabbar.changed.connect(self._switch)
        tlay.addWidget(self._tabbar)
        outer.addWidget(tabhost)

        self._stack = QStackedWidget()
        self._ov   = _AnalyticsOverview(manager, doc, year, month)
        self.navigate_to = self._ov.navigate_to
        self._inc  = LedgerDetailPage("income",  manager, doc, year, month, self._changed)
        self._exp  = LedgerDetailPage("expense", manager, doc, year, month, self._changed)
        for w in (self._ov, self._inc, self._exp):
            self._stack.addWidget(w)
        outer.addWidget(self._stack, 1)

    def _switch(self, name):
        self._stack.setCurrentWidget(
            {"Overview": self._ov, "Income": self._inc, "Expenses": self._exp}[name])

    def _changed(self):
        self._on_change()
        cur = self._stack.currentWidget()
        if cur in (self._inc, self._exp):
            doc, y, m = self._inc.doc, self._inc.year, self._inc.month
            self._ov.set_context(doc, y, m)

    def set_context(self, doc, year, month):
        self._ov.set_context(doc, year, month)
        self._inc.set_context(doc, year, month)
        self._exp.set_context(doc, year, month)


def _leaf_expenses(doc):
    """Return [(name, amount), ...] for all leaf expense nodes."""
    out = []
    def scan(nodes):
        for n in nodes:
            if n.get("children"):
                scan(n["children"])
            else:
                out.append((n["name"], float(n.get("amount", 0))))
    scan(doc.get("expenses", []))
    return out


def _find_leaf(doc, name):
    """Return the first leaf expense node with the given name, or None."""
    def scan(nodes):
        for n in nodes:
            if n.get("children"):
                r = scan(n["children"])
                if r:
                    return r
            elif n.get("name") == name:
                return n
        return None
    return scan(doc.get("expenses", []))


def _auto_saved(manager, linked_names):
    """Sum the linked expense amounts across all stored months."""
    total = 0.0
    for y, m in manager.list_months():
        leaf_map = {n: a for n, a in _leaf_expenses(manager.load_month(y, m))}
        for name in linked_names:
            total += leaf_map.get(name, 0.0)
    return total


class GoalsPage(QWidget):
    def __init__(self, manager, doc, year, month, on_change):
        super().__init__()
        self.dm, self.on_change = manager, on_change
        self.year, self.month = year, month
        self.goals_doc = manager.load_goals()
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 18); lay.setSpacing(14)

        # this-month targets
        trow, self.tiles = tile_row(["Actual P&L", "Target P&L", "Savings rate"])
        lay.addLayout(trow)
        mcard, mlay = card()
        prog = QHBoxLayout(); prog.setSpacing(10)
        prog.addWidget(label("Progress to target", T.TEXT_MUTED, 12))
        self.target_bar = ProgressBar(0, T.GREEN, 10)
        prog.addWidget(self.target_bar, 1)
        self.target_pct = label("", T.ACCENT, 12, bold=True)
        prog.addWidget(self.target_pct)
        mlay.addLayout(prog)
        lay.addWidget(mcard)

        # savings goals
        gcard, glay = card()
        gh = QHBoxLayout()
        gh.addWidget(label("Savings goals", T.TEXT, 13, bold=True))
        gh.addStretch(1)
        add = Clickable("+ Add goal", T.TEXT_MUTED, 12, hover=T.ACCENT)
        add.clicked.connect(self._add_goal)
        gh.addWidget(add)
        glay.addLayout(gh)
        self.goals_box = QVBoxLayout(); self.goals_box.setSpacing(13)
        glay.addLayout(self.goals_box)
        lay.addWidget(gcard)

        # monthly targets editor
        ecard, elay = card()
        elay.addWidget(label("Edit monthly targets", T.TEXT_MUTED, 12))
        self.target_in = _spin(0, 1_000_000)
        self.weekly_in = _spin(0, 1_000_000)
        for cap, w in (("Target P&L", self.target_in),
                       ("Weekly budget", self.weekly_in)):
            r = QHBoxLayout()
            r.addWidget(label(cap, T.TEXT, 12)); r.addStretch(1); r.addWidget(w)
            elay.addLayout(r)
        save = _button("Save targets", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        save.clicked.connect(self._save_targets)
        elay.addSpacing(2); elay.addWidget(save, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(ecard)
        lay.addStretch(1)
        outer.addWidget(scrollable(content))

    def set_context(self, doc, year, month):
        self.doc = doc
        self.year, self.month = year, month
        self.goals_doc = self.dm.load_goals()
        cur = doc.get("currency", "$")
        self.target_in.setPrefix(cur)
        self.weekly_in.setPrefix(cur)
        pnl, target = B.pnl(doc), doc.get("target_pnl", 0)
        self.tiles[0].set_value(money(pnl, cur), T.GREEN if pnl >= 0 else T.RED)
        self.tiles[1].set_value(money(target, cur, signed=False), T.TEXT)
        self.tiles[2].set_value(f"{B.savings_rate(doc) * 100:.1f}%", T.ACCENT)
        frac = (pnl / target) if target > 0 else (1.0 if pnl > 0 else 0.0)
        self.target_bar.set_frac(frac, T.GREEN if frac >= 1 else T.AMBER,
                                 target=1.0)
        self.target_pct.setText(f"{frac * 100:.0f}%")
        self.target_in.setValue(target)
        self.weekly_in.setValue(doc.get("weekly_budget", 0))
        self._rebuild_goals(cur)

    def _rebuild_goals(self, cur):
        clear_layout(self.goals_box)
        goals = self.goals_doc.get("goals", [])
        if not goals:
            self.goals_box.addWidget(label("No goals yet — add one above.",
                                           T.TEXT_DIM, 12))
            return
        all_months = self.dm.list_months()
        pnl_vals = [B.pnl(self.dm.load_month(y, m)) for y, m in all_months[-6:]]
        avg_pnl = sum(pnl_vals) / len(pnl_vals) if pnl_vals else 0.0
        all_leaves = _leaf_expenses(getattr(self, "doc", {}))
        save_needed = False
        for g in goals:
            if g.get("linked"):
                auto = _auto_saved(self.dm, g["linked"])
                if abs(auto - g.get("saved", 0)) > 0.001:
                    g["saved"] = auto
                    save_needed = True
        if save_needed:
            self.dm.save_goals(self.goals_doc)
        for g in goals:
            self.goals_box.addLayout(self._goal_row(g, cur, avg_pnl, all_leaves))

    def _goal_row(self, g, cur, avg_pnl=0.0, all_leaves=None):
        from datetime import date as _dt
        frac = (g["saved"] / g["target"]) if g["target"] > 0 else 0.0
        done = frac >= 1
        box = QVBoxLayout(); box.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(label(g["name"], T.TEXT, 13, bold=True))
        head.addSpacing(8)
        head.addWidget(label("✓ reached" if done else f"{frac * 100:.0f}%",
                             T.GREEN if done else T.TEXT_MUTED, 11, bold=done))
        head.addStretch(1)
        head.addWidget(label(f"{money(g['saved'], cur, signed=False)} / "
                             f"{money(g['target'], cur, signed=False)}",
                             T.TEXT_MUTED, 12))
        lnk = Clickable("⊕", T.TEXT_DIM, 12, hover=T.ACCENT)
        lnk.setToolTip("Link an expense to this goal")
        lnk.clicked.connect(lambda _=False, gg=g, btn=lnk: self._link_expense(gg, btn))
        ed = Clickable("✎", T.TEXT_DIM, 12, hover=T.TEXT)
        ed.clicked.connect(lambda _=False, gg=g: self._edit_goal(gg))
        rm = Clickable("✕", T.TEXT_DIM, 12, hover=T.RED)
        rm.clicked.connect(lambda _=False, gg=g: self._delete_goal(gg))
        head.addSpacing(8); head.addWidget(lnk); head.addWidget(ed); head.addWidget(rm)
        box.addLayout(head)
        box.addWidget(ProgressBar(min(frac, 1.0), T.GREEN if done else T.SERIES[1], 10))

        leaf_map = {n: a for n, a in (all_leaves or [])}
        linked = g.get("linked", [])
        if linked:
            chip_row = QHBoxLayout(); chip_row.setSpacing(4)
            for ln in linked:
                amt = leaf_map.get(ln, 0)
                btn = Clickable(f"→ {ln}  {money(-amt, cur)}/mo", T.ACCENT, 10,
                                hover=T.GREEN_BRIGHT)
                btn.setToolTip("Click for details")
                btn.clicked.connect(lambda _=False, nm=ln: self._show_expense_detail(nm))
                x = Clickable("×", T.TEXT_DIM, 10, hover=T.RED)
                x.setToolTip("Unlink")
                x.clicked.connect(lambda _=False, gg=g, nm=ln: self._unlink_expense(gg, nm))
                chip_row.addWidget(btn)
                chip_row.addWidget(x)
                chip_row.addSpacing(8)
            chip_row.addStretch(1)
            box.addLayout(chip_row)

        if not done:
            monthly_contrib = (sum(leaf_map.get(n, 0) for n in linked)
                               if linked else max(0.0, avg_pnl))
            eta = B.goal_eta(g["saved"], g["target"], monthly_contrib, _dt.today())
            if eta["months"]:
                src = (f"linked {money(monthly_contrib, cur)}/mo"
                       if linked else f"avg {money(monthly_contrib, cur)}/mo")
                proj = (f"on track by {dm.MONTH_ABBR[eta['month']]} {eta['year']}"
                        f"  ·  ~{eta['months']} mo  ({src})")
                box.addWidget(label(proj, T.TEXT_DIM, 10))
                if len(eta["projection"]) > 1:
                    chart = LineChart()
                    chart.setFixedHeight(96)
                    chart.setCursor(Qt.CursorShape.ArrowCursor)
                    chart.set_series(eta["projection"], target=g["target"],
                                     fill=True, highlight_last=False,
                                     currency=cur, color=T.SERIES[1])
                    box.addWidget(chart)
            else:
                box.addWidget(label(
                    "Link an expense or build savings history to project completion",
                    T.TEXT_DIM, 10))

        return box

    def _save_goals(self):
        self.dm.save_goals(self.goals_doc)
        self._rebuild_goals(self.doc.get("currency", "$"))

    def _add_goal(self):
        g = GoalDialog.create(self, self.doc.get("currency", "$"))
        if g:
            self.goals_doc.setdefault("goals", []).append(g)
            self._save_goals()

    def _edit_goal(self, g):
        if GoalDialog.edit(self, g, self.doc.get("currency", "$")):
            self._save_goals()

    def _delete_goal(self, g):
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete", f"Delete goal \"{g.get('name', '')}\"?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.goals_doc["goals"] = [x for x in self.goals_doc.get("goals", [])
                                   if x is not g]
        self._save_goals()

    def _link_expense(self, g, btn):
        leaves = _leaf_expenses(getattr(self, "doc", {}))
        if not leaves:
            return
        cur = getattr(self, "doc", {}).get("currency", "$")
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{T.BG_CARD};color:{T.TEXT};"
            f"border:1px solid {T.BORDER_LIGHT};}}"
            f"QMenu::item:selected{{background:{T.BG_HOVER};}}")
        linked = g.get("linked", [])
        for name, amt in leaves:
            tick = "✓ " if name in linked else "    "
            act = menu.addAction(f"{tick}{name}  ({money(-amt, cur)}/mo)")
            act.setData(name)
        chosen = menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))
        if chosen:
            nm = chosen.data()
            lk = g.setdefault("linked", [])
            if nm in lk:
                lk.remove(nm)
            else:
                lk.append(nm)
            self._save_goals()

    def _unlink_expense(self, g, name):
        lk = g.get("linked", [])
        if name in lk:
            lk.remove(name)
            self._save_goals()

    def _show_expense_detail(self, name):
        node = _find_leaf(getattr(self, "doc", {}), name)
        cur  = getattr(self, "doc", {}).get("currency", "$")
        dlg  = QDialog(self)
        dlg.setWindowTitle(name)
        dlg.setFixedWidth(300)
        dlg.setStyleSheet(
            f"QDialog{{background:{T.BG_CARD};}}"
            f"QLabel{{background:transparent;}}")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10); lay.setContentsMargins(18, 16, 18, 16)
        lay.addWidget(label(name, T.TEXT, 14, bold=True))
        if node:
            amt = float(node.get("amount", 0))
            rows = [
                ("Amount",  money(-amt, cur) + "/mo"),
            ]
            due = node.get("due")
            if due and len(due) >= 10:
                rows.append(("Due", f"{due[8:10]}/{due[5:7]}/{due[:4]}"))
            repeat = node.get("repeat")
            if repeat:
                every = repeat.get("every", 1)
                unit  = repeat.get("unit", "month")
                rows.append(("Recurs", f"every {every} {unit}{'s' if every != 1 else ''}"))
            paid = node.get("paid", False)
            rows.append(("Status", "Paid ✓" if paid else "Unpaid"))
            for cap, val in rows:
                r = QHBoxLayout()
                r.addWidget(label(cap, T.TEXT_MUTED, 12))
                r.addStretch(1)
                r.addWidget(label(val, T.GREEN if (cap == "Status" and paid) else T.TEXT, 12, bold=True))
                lay.addLayout(r)
        else:
            lay.addWidget(label("Not found in current month.", T.TEXT_DIM, 11))
        lay.addSpacing(4)
        close = _button("Close", T.TEXT_MUTED, T.BG_HOVER, T.BORDER)
        close.clicked.connect(dlg.accept)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignLeft)
        dlg.exec()

    def _save_targets(self):
        tp = float(self.target_in.value())
        wb = float(self.weekly_in.value())
        if hasattr(self.dm, "set_period_setting"):     # flat store
            self.dm.set_period_setting(self.year, self.month, "target_pnl", tp)
            self.dm.set_period_setting(self.year, self.month, "weekly_budget", wb)
        else:
            self.doc["target_pnl"] = tp
            self.doc["weekly_budget"] = wb
        self.on_change()
        self.set_context(self.dm.load_month(self.year, self.month),
                         self.year, self.month)


# --------------------------------------------------------------------------- #
#  History – totals, cumulative savings, month list
# --------------------------------------------------------------------------- #
class HistoryPage(QWidget):
    def __init__(self, manager, goto):
        super().__init__()
        self.dm, self.goto = manager, goto
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 18); lay.setSpacing(14)

        trow, self.tiles = tile_row(
            ["Total saved", "Avg / month", "Best month", "Months tracked"])
        lay.addLayout(trow)

        ccard, clay = card()
        clay.addWidget(label("Cumulative savings", T.TEXT_MUTED, 12))
        self.cum = LineChart(); self.cum.setMinimumHeight(180)
        clay.addWidget(self.cum)
        lay.addWidget(ccard)

        lcard, llay = card((10, 12, 10, 10))
        llay.addWidget(label("Monthly history", T.TEXT_MUTED, 12))
        self.rows = QVBoxLayout(); self.rows.setSpacing(3)
        llay.addLayout(self.rows)
        lay.addWidget(lcard)
        lay.addStretch(1)
        outer.addWidget(scrollable(content))

    def set_context(self, doc, year, month):
        cur = doc.get("currency", "$")
        today = date.today()
        months = [(y, m) for y, m in self.dm.list_months()
                  if (y, m) < (today.year, today.month)]
        data = [(y, m, self.dm.load_month(y, m)) for y, m in months]
        pnls = [B.pnl(d) for _, _, d in data]
        total = sum(pnls)
        self.tiles[0].set_value(money(total, cur), T.GREEN if total >= 0 else T.RED)
        self.tiles[1].set_value(money(total / len(pnls) if pnls else 0, cur))
        if data:
            by, bm, bd = max(data, key=lambda t: B.pnl(t[2]))
            self.tiles[2].set_value(f"{dm.MONTH_ABBR[bm]} {by}", T.ACCENT)
        else:
            self.tiles[2].set_value("—")
        self.tiles[3].set_value(str(len(months)))

        run, series = 0.0, []
        for y, m, d in data:
            run += B.pnl(d)
            series.append((dm.MONTH_ABBR[m], run))
        self.cum.set_series(series, fill=True, currency=cur)

        clear_layout(self.rows)
        for (y, m, d) in reversed(data):
            self.rows.addWidget(self._month_row(y, m, d, cur))
        self.rows.addStretch(1)

    def _month_row(self, y, m, d, cur):
        inc = B.income_total(d)
        exp = B.expense_total(d)
        p = inc - exp
        sr = (p / inc) if inc else 0.0
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{text-align:left; background:transparent; border:none;"
            f"border-radius:0px; padding:10px 12px;}}"
            f"QPushButton:hover{{background:{T.BG_HOVER};}}")
        lyt = QHBoxLayout(btn); lyt.setContentsMargins(2, 0, 6, 0); lyt.setSpacing(10)
        lyt.addWidget(label(f"{dm.MONTH_NAMES[m]} {y}", T.TEXT, 13, bold=True))
        bar = ProgressBar(sr, T.GREEN, 7)
        bar.setFixedWidth(120)
        lyt.addWidget(bar)
        lyt.addStretch(1)
        lyt.addWidget(label(f"in {money(inc, cur)}", T.TEXT_MUTED, 11))
        lyt.addWidget(label(f"out {money(-exp, cur)}", T.TEXT_MUTED, 11))
        lyt.addSpacing(8)
        lyt.addWidget(label(money(p, cur), T.GREEN if p >= 0 else T.RED, 14, bold=True))
        btn.clicked.connect(lambda _=False, yy=y, mm=m: self.goto(yy, mm))
        return btn


# --------------------------------------------------------------------------- #
#  Settings – currency + CSV export
# --------------------------------------------------------------------------- #
class SettingsPage(QWidget):
    reset_requested   = pyqtSignal()
    week_style_changed = pyqtSignal(str)   # "iso_week" | "monday_in_month"
    sidebar_changed   = pyqtSignal()       # hidden_tabs changed

    _WEEK_LABELS = {"ISO weeks (Mon–Sun, cross-month)": "iso_week",
                    "Month-aligned weeks (reset on the 1st)": "monday_in_month"}

    def __init__(self, manager, on_change):
        super().__init__()
        self.dm, self.on_change = manager, on_change
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 18); lay.setSpacing(14)

        pcard, play = card()
        play.addWidget(label("Currency symbol", T.TEXT, 12))
        self.currency = QComboBox(); self.currency.addItems(["$", "£", "€", "¥", "₹"])
        self.currency.setFixedWidth(90)
        self.currency.currentTextChanged.connect(self._save_currency)
        play.addWidget(self.currency)
        lay.addWidget(pcard)

        wcard, wlay = card()
        wlay.addWidget(label("Week view style", T.TEXT, 12))
        wlay.addWidget(label("How the “Week” lens slices time when you review by week.",
                             T.TEXT_MUTED, 11))
        self.week_style = QComboBox(); self.week_style.addItems(list(self._WEEK_LABELS))
        self.week_style.setFixedWidth(320)
        cur_style = (self.dm.settings().get("week_style", "iso_week")
                     if hasattr(self.dm, "settings") else "iso_week")
        inv = {v: k for k, v in self._WEEK_LABELS.items()}
        self.week_style.setCurrentText(inv.get(cur_style, list(self._WEEK_LABELS)[0]))
        self.week_style.currentTextChanged.connect(self._save_week_style)
        wlay.addWidget(self.week_style)
        lay.addWidget(wcard)

        # ── Sidebar tabs (show / hide) ──────────────────────────────────── #
        from widgets import Sidebar
        scard, slay = card()
        slay.addWidget(label("Sidebar tabs", T.TEXT, 13, bold=True))
        slay.addWidget(label("Show or hide tabs in the left sidebar "
                             "(Overview and Settings always stay).", T.TEXT_MUTED, 11))
        hidden = set(self.dm.settings().get("hidden_tabs", []))
        self._tab_checks = {}
        crow = QHBoxLayout(); crow.setSpacing(18)
        for key, lbl in Sidebar.HIDEABLE:
            cb = QCheckBox(lbl); cb.setChecked(key not in hidden)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"color:{T.TEXT_MUTED};")
            cb.toggled.connect(lambda vis, k=key: self._toggle_tab(k, vis))
            self._tab_checks[key] = cb
            crow.addWidget(cb)
        crow.addStretch(1)
        slay.addLayout(crow)
        lay.addWidget(scard)

        ecard, elay = card()
        elay.addWidget(label("Export data (CSV)", T.TEXT, 13, bold=True))
        elay.addWidget(label("Open the resulting file in Excel, Sheets or Numbers.",
                             T.TEXT_MUTED, 11))
        brow = QHBoxLayout(); brow.setSpacing(10)
        b1 = _button("Export this month", T.TEXT, T.BG_INPUT, T.BORDER)
        b1.clicked.connect(self._export_month)
        b2 = _button("Export all months", T.TEXT, T.BG_INPUT, T.BORDER)
        b2.clicked.connect(self._export_all)
        brow.addWidget(b1); brow.addWidget(b2); brow.addStretch(1)
        elay.addLayout(brow)
        self.status = label("", T.GREEN, 11)
        elay.addWidget(self.status)
        lay.addWidget(ecard)

        # ── Connect bank accounts (file import — no logins) ──────────────── #
        icard, ilay = card()
        ilay.addWidget(label("Connect bank accounts (ANZ / ANZ Plus)", T.TEXT, 13, bold=True))
        desc = label(
            "Export your transactions from ANZ or ANZ Plus internet banking as a "
            "CSV or OFX file, then import it here. Your bank login is never entered "
            "into this app. Imported spend feeds the Budget page.", T.TEXT_MUTED, 11)
        desc.setWordWrap(True); ilay.addWidget(desc)

        irow = QHBoxLayout(); irow.setSpacing(10)
        irow.addWidget(label("Account", T.TEXT_MUTED, 11))
        self.acct = QComboBox(); self.acct.addItems(["ANZ", "ANZ Plus"])
        self.acct.setFixedWidth(120)
        irow.addWidget(self.acct)
        imp = _button("Import CSV / OFX…", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        imp.clicked.connect(self._import_bank)
        clr = _button("Clear imported", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
        clr.clicked.connect(self._clear_imported)
        irow.addWidget(imp); irow.addWidget(clr); irow.addStretch(1)
        ilay.addLayout(irow)
        self.import_status = label("", T.TEXT_MUTED, 11)
        ilay.addWidget(self.import_status)
        lay.addWidget(icard)
        self._refresh_import_status()

        # ── Categorisation rules ────────────────────────────────────────── #
        rcard, rly = card()
        rly.addWidget(label("Categorisation rules", T.TEXT, 13, bold=True))
        rly.addWidget(label("When an imported transaction's description contains the "
                            "text, it's filed under the category.", T.TEXT_MUTED, 11))
        self.rules_box = QVBoxLayout(); self.rules_box.setSpacing(4)
        rly.addLayout(self.rules_box)
        rrow = QHBoxLayout(); rrow.setSpacing(8)
        self.rule_match = QLineEdit(); self.rule_match.setPlaceholderText("contains… (e.g. woolworths)")
        self.rule_cat = QLineEdit(); self.rule_cat.setPlaceholderText("category (e.g. Groceries)")
        _ist = (f"background:{T.BG_INPUT}; color:{T.TEXT};"
                f"border:1px solid {T.BORDER_LIGHT}; padding:5px 7px;")
        self.rule_match.setStyleSheet(_ist); self.rule_cat.setStyleSheet(_ist)
        addr = _button("Add rule", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        addr.clicked.connect(self._add_rule)
        rrow.addWidget(self.rule_match, 1); rrow.addWidget(self.rule_cat, 1); rrow.addWidget(addr)
        rly.addLayout(rrow)
        lay.addWidget(rcard)
        self._refresh_rules()

        # ── Live bank sync (via Basiq open-banking) — beta ──────────────── #
        lc, lly = card()
        lly.addWidget(label("Live bank sync (via Basiq) — beta", T.TEXT, 13, bold=True))
        ldesc = label(
            "Pull ANZ / ANZ Plus transactions automatically. Requires a free Basiq "
            "developer API key (dashboard.basiq.io). You authenticate on ANZ’s own "
            "page during consent — your bank password never enters this app. Only your "
            "Basiq API key is stored locally.", T.TEXT_MUTED, 11)
        ldesc.setWordWrap(True); lly.addWidget(ldesc)
        st = (self.dm.settings() if hasattr(self.dm, "settings") else {})
        krow = QHBoxLayout(); krow.setSpacing(8)
        krow.addWidget(label("API key", T.TEXT_MUTED, 11))
        self.basiq_key = QLineEdit(st.get("basiq_api_key", ""))
        self.basiq_key.setPlaceholderText("Basiq API key")
        self.basiq_key.setStyleSheet(
            f"background:{T.BG_INPUT}; color:{T.TEXT}; border:1px solid {T.BORDER_LIGHT}; padding:5px 7px;")
        krow.addWidget(self.basiq_key, 1)
        krow.addWidget(label("User id", T.TEXT_MUTED, 11))
        self.basiq_user = QLineEdit(st.get("basiq_user_id", ""))
        self.basiq_user.setPlaceholderText("(set after Connect)")
        self.basiq_user.setFixedWidth(180)
        self.basiq_user.setStyleSheet(self.basiq_key.styleSheet())
        krow.addWidget(self.basiq_user)
        lly.addLayout(krow)
        brow = QHBoxLayout(); brow.setSpacing(10)
        conn = _button("Connect ANZ", T.ACCENT, T.BG_INPUT, T.BORDER)
        conn.clicked.connect(self._connect_live)
        synb = _button("Sync now", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        synb.clicked.connect(self._sync_live)
        brow.addWidget(conn); brow.addWidget(synb); brow.addStretch(1)
        lly.addLayout(brow)
        self.live_status = label(
            "Not connected. This is a scaffold — the live calls are untested until "
            "you add a key; verify the first sync.", T.TEXT_DIM, 11)
        self.live_status.setWordWrap(True)
        lly.addWidget(self.live_status)
        lay.addWidget(lc)

        # ── Modules (plugins) ───────────────────────────────────────────── #
        mcard, mly = card()
        mly.addWidget(label("Modules", T.TEXT, 13, bold=True))
        mly.addWidget(label("Drop a Python file defining register(api) in the modules "
                            "folder to add your own page. Only add code you trust.",
                            T.TEXT_MUTED, 11))
        self._mod_path = label("", T.TEXT_DIM, 10); self._mod_path.setWordWrap(True)
        mly.addWidget(self._mod_path)
        self._mod_box = QVBoxLayout(); self._mod_box.setSpacing(4)
        mly.addLayout(self._mod_box)
        lay.addWidget(mcard)

        note = label(f"Data lives as JSON under  {dm.DATA_DIR}  — one file per "
                     f"month, plus goals.json.", T.TEXT_MUTED, 11)
        note.setWordWrap(True)
        lay.addWidget(note)

        # ── Danger zone ──────────────────────────────────────────────────── #
        dcard = QFrame(); dcard.setObjectName("DangerCard")
        dcard.setStyleSheet(
            f"#DangerCard{{background:{T.RED_BG}; border:1px solid {T.RED_BORDER};"
            f"border-radius:0px;}}")
        dlay = QVBoxLayout(dcard)
        dlay.setContentsMargins(18, 14, 18, 14); dlay.setSpacing(8)
        dlay.addWidget(label("Danger zone", T.RED, 13, bold=True))
        dlay.addWidget(label(
            "Permanently deletes all months, goals and settings. "
            "A one-off .bak backup is kept in the data folder.", T.TEXT_MUTED, 11))
        rst = QPushButton("Reset all budget data")
        rst.setCursor(Qt.CursorShape.PointingHandCursor)
        rf = QFont(T.FONT_FAMILY); rf.setPixelSize(12); rst.setFont(rf)
        rst.setStyleSheet(
            f"QPushButton{{background:transparent; color:{T.RED};"
            f"border:1px solid {T.RED_BORDER}; border-radius:0px; padding:7px 16px;}}"
            f"QPushButton:hover{{background:{T.RED}; color:{T.BG_APP};"
            f"border-color:{T.RED};}}")
        rst.clicked.connect(self._confirm_reset)
        dlay.addWidget(rst, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(dcard)
        lay.addStretch(1)
        outer.addWidget(scrollable(content))

    def set_context(self, doc, year, month):
        self.doc = doc
        self.currency.blockSignals(True)
        self.currency.setCurrentIndex(max(0, self.currency.findText(
            doc.get("currency", "$"))))
        self.currency.blockSignals(False)
        self.status.setText("")
        self._refresh_import_status()
        self._refresh_rules()
        hidden = set(self.dm.settings().get("hidden_tabs", []))
        for key, cb in getattr(self, "_tab_checks", {}).items():
            cb.blockSignals(True); cb.setChecked(key not in hidden); cb.blockSignals(False)

    def _save_currency(self, text):
        if hasattr(self.dm, "settings"):               # flat store: currency is global
            self.dm.settings()["currency"] = text
            self.dm.save()
            self.on_change()
        elif getattr(self, "doc", None):
            self.doc["currency"] = text
            self.on_change()

    def _save_week_style(self, text):
        style = self._WEEK_LABELS.get(text, "iso_week")
        if hasattr(self.dm, "settings"):
            self.dm.settings()["week_style"] = style
            self.dm.save()
        self.week_style_changed.emit(style)

    def set_module_info(self, loaded, errors, path):
        """Show which user modules loaded (and any errors) in the Modules card."""
        self._mod_path.setText(f"Folder: {path}")
        clear_layout(self._mod_box)
        if not loaded and not errors:
            self._mod_box.addWidget(label("No modules installed.", T.TEXT_DIM, 11))
        for fname in loaded:
            self._mod_box.addWidget(label(f"✓ {fname}", T.GREEN, 11))
        for fname, _err in errors:
            row = label(f"✕ {fname} — failed to load", T.RED, 11)
            row.setToolTip(str(_err)[-600:])
            self._mod_box.addWidget(row)

    def _toggle_tab(self, key, visible):
        hidden = set(self.dm.settings().get("hidden_tabs", []))
        hidden.discard(key) if visible else hidden.add(key)
        self.dm.settings()["hidden_tabs"] = sorted(hidden)
        self.dm.save()
        self.sidebar_changed.emit()

    def _export_month(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export this month", f"budget_{self.doc['month']}.csv",
            "CSV files (*.csv)")
        if path:
            try:
                X.export_month_csv(self.doc, path)
            except OSError as e:                # locked (open in Excel) / read-only
                self._flash_status(self.status, f"Could not save: {e}", T.RED)
                return
            self._flash_status(self.status, f"Saved {os.path.basename(path)}", T.GREEN)

    def _confirm_reset(self):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Reset all budget data")
        msg.setText("This will permanently erase every month, goal and setting.")
        msg.setInformativeText("Are you absolutely sure? A one-off backup is kept "
                               "as items.json.bak / goals.json.bak in the data folder.")
        msg.setIcon(QMessageBox.Icon.Warning)
        yes = msg.addButton("Yes, delete everything", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg.exec()
        if msg.clickedButton() is yes:
            self.reset_requested.emit()

    def _export_all(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export all months", "budget_history.csv", "CSV files (*.csv)")
        if path:
            try:
                X.export_history_csv(self.dm, path)
            except OSError as e:
                self._flash_status(self.status, f"Could not save: {e}", T.RED)
                return
            self._flash_status(self.status, f"Saved {os.path.basename(path)}", T.GREEN)

    # -- bank import ------------------------------------------------------ #
    def _flash_status(self, lbl, text, color):
        """Show a transient status message that clears itself after a few seconds."""
        lbl.setText(text)
        lbl.setStyleSheet(f"color:{color}; background:transparent;")
        QTimer.singleShot(4000, lambda: lbl.text() == text and lbl.setText(""))

    def _refresh_import_status(self):
        # neutral colour — clears any leftover red/amber from a previous import
        self.import_status.setStyleSheet(f"color:{T.TEXT_MUTED}; background:transparent;")
        n = len(self.dm.transactions()) if hasattr(self.dm, "transactions") else 0
        if n:
            uncat = sum(1 for t in self.dm.transactions() if not t.get("category"))
            self.import_status.setText(
                f"{n} transaction{'s' if n != 1 else ''} imported"
                + (f"  ·  {uncat} uncategorised" if uncat else "  ·  all categorised"))
        else:
            self.import_status.setText("No transactions imported yet.")

    def _import_bank(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import bank transactions", "",
            "Bank exports (*.csv *.ofx *.qfx);;All files (*.*)")
        if not path:
            return
        try:
            raw = IMP.parse_file(path)
        except Exception as e:                         # malformed / unreadable file
            self.import_status.setText(f"Could not read file: {e}")
            self.import_status.setStyleSheet(f"color:{T.RED}; background:transparent;")
            return
        if not raw:
            self.import_status.setText(
                "No transactions found — is this an ANZ CSV/OFX export?")
            self.import_status.setStyleSheet(f"color:{T.AMBER}; background:transparent;")
            return
        res = self.dm.import_transactions(raw, account=self.acct.currentText())
        self.import_status.setStyleSheet(f"color:{T.GREEN}; background:transparent;")
        self.import_status.setText(
            f"Imported {res['added']} new ({res['categorised']} auto-categorised), "
            f"{res['skipped']} duplicate(s) skipped.")
        self.on_change()                               # refresh Budget etc.

    def _clear_imported(self):
        from PyQt6.QtWidgets import QMessageBox
        if not (hasattr(self.dm, "transactions") and self.dm.transactions()):
            return
        reply = QMessageBox.question(
            self, "Clear imported", "Remove all imported transactions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.dm.clear_transactions()
            self._refresh_import_status()
            self.on_change()

    # -- categorisation rules --------------------------------------------- #
    def _refresh_rules(self):
        clear_layout(self.rules_box)
        rules = self.dm.rules() if hasattr(self.dm, "rules") else []
        if not rules:
            self.rules_box.addWidget(label("No rules yet.", T.TEXT_DIM, 11))
            return
        for i, r in enumerate(rules):
            row = QHBoxLayout(); row.setSpacing(6)
            row.addWidget(label(f"“{r.get('match', '')}”", T.TEXT, 11))
            row.addWidget(label("→", T.TEXT_DIM, 11))
            row.addWidget(label(r.get("category", ""), T.ACCENT, 11, bold=True))
            row.addStretch(1)
            rm = Clickable("✕", T.TEXT_DIM, 11, hover=T.RED)
            rm.setToolTip("Delete rule")
            rm.clicked.connect(lambda _=False, idx=i: self._remove_rule(idx))
            row.addWidget(rm)
            self.rules_box.addLayout(row)

    def _add_rule(self):
        m = self.rule_match.text().strip()
        c = self.rule_cat.text().strip()
        if not (m and c):
            return
        self.dm.add_rule(m, c)                 # recategorises existing transactions
        self.rule_match.clear(); self.rule_cat.clear()
        self._refresh_rules(); self._refresh_import_status(); self.on_change()

    def _remove_rule(self, idx):
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete rule", "Delete this categorisation rule?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.dm.remove_rule(idx)
        self._refresh_rules(); self._refresh_import_status(); self.on_change()

    # -- live bank sync (Basiq) ------------------------------------------- #
    def _save_basiq(self):
        s = self.dm.settings()
        s["basiq_api_key"] = self.basiq_key.text().strip()
        s["basiq_user_id"] = self.basiq_user.text().strip()
        self.dm.save()

    def _connect_live(self):
        self._save_basiq()
        import bank_sync, webbrowser
        key = self.basiq_key.text().strip()
        if not key:
            self.live_status.setText("Enter your Basiq API key first "
                                     "(create one free at dashboard.basiq.io).")
            return
        try:
            token = bank_sync.server_token(key)
            uid = self.basiq_user.text().strip() or bank_sync.create_user(token)
            self.basiq_user.setText(uid)
            self.dm.settings()["basiq_user_id"] = uid; self.dm.save()
            url = bank_sync.consent_url(token, uid)
            webbrowser.open(url)
            self.live_status.setStyleSheet(f"color:{T.TEXT_MUTED}; background:transparent;")
            self.live_status.setText("Opened ANZ’s consent page in your browser. "
                                     "Approve there, then click “Sync now”.")
        except bank_sync.BankSyncError as e:
            self.live_status.setStyleSheet(f"color:{T.RED}; background:transparent;")
            self.live_status.setText(f"Connect failed: {e}")

    def _sync_live(self):
        self._save_basiq()
        import bank_sync
        key = self.basiq_key.text().strip()
        uid = self.basiq_user.text().strip()
        try:
            res = bank_sync.sync(self.dm, key, uid)
            self.live_status.setStyleSheet(f"color:{T.GREEN}; background:transparent;")
            self.live_status.setText(
                f"Synced {res['added']} new ({res['categorised']} categorised), "
                f"{res['skipped']} duplicate(s) skipped.")
            self._refresh_import_status()
            self.on_change()
        except bank_sync.BankSyncError as e:
            self.live_status.setStyleSheet(f"color:{T.RED}; background:transparent;")
            self.live_status.setText(f"Sync failed: {e}")


# --------------------------------------------------------------------------- #
#  Onboarding wizard (first launch)
# --------------------------------------------------------------------------- #
class OnboardingDialog(QDialog):
    """Step-by-step wizard shown on first launch to set up the budget."""

    def __init__(self, parent, today: date):
        super().__init__(parent)
        self.setWindowTitle("Welcome")
        self.setModal(True)
        self.setFixedSize(560, 480)
        self.today = today
        self.result_doc = None

        self._income_pairs: list[tuple] = []   # (name_le, amt_le, recur_combo)
        self._expense_pairs: list[tuple] = []  # (name_le, amt_le)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        # Pages: 0=welcome  1=income  2=expenses  3=targets  4=done
        self._stack.addWidget(self._p_welcome())
        self._stack.addWidget(self._p_income())
        self._stack.addWidget(self._p_expenses())
        self._stack.addWidget(self._p_targets())
        self._stack.addWidget(self._p_done())

    # ── helpers ────────────────────────────────────────────────────────── #
    def _go(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _btn(self, text, primary=False):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        f = QFont(T.FONT_FAMILY); f.setPixelSize(13); b.setFont(f)
        if primary:
            b.setStyleSheet(
                f"QPushButton{{background:{T.ACCENT};color:{T.ON_ACCENT};border:none;"
                f"padding:8px 22px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{T.GREEN_BRIGHT};}}")
        else:
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{T.TEXT_MUTED};"
                f"border:1px solid {T.BORDER};padding:8px 16px;}}"
                f"QPushButton:hover{{color:{T.TEXT};border-color:{T.BORDER_LIGHT};}}")
        return b

    def _nav_row(self, back_idx=None, next_fn=None, next_text="Next →", skip_fn=None):
        row = QHBoxLayout(); row.setSpacing(8)
        if back_idx is not None:
            b = self._btn("← Back"); b.clicked.connect(lambda: self._go(back_idx))
            row.addWidget(b)
        row.addStretch(1)
        if skip_fn:
            s = self._btn("Skip")
            s.setStyleSheet(f"QPushButton{{background:transparent;color:{T.TEXT_DIM};"
                            f"border:none;padding:8px 14px;}}"
                            f"QPushButton:hover{{color:{T.TEXT_MUTED};}}")
            s.clicked.connect(skip_fn)
            row.addWidget(s)
        if next_fn:
            n = self._btn(next_text, primary=True); n.clicked.connect(next_fn)
            row.addWidget(n)
        return row

    def _progress(self, step: int):
        row = QHBoxLayout(); row.setSpacing(3)
        for i in range(3):
            seg = QFrame(); seg.setFixedHeight(3)
            seg.setStyleSheet(f"background:{T.ACCENT if i < step else T.BORDER};")
            row.addWidget(seg, 1)
        return row

    def _shell(self, step: int, title: str, sub: str):
        """Return (page_widget, page_layout, content_vbox)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(44, 32, 44, 28); lay.setSpacing(0)
        lay.addLayout(self._progress(step))
        lay.addSpacing(22)
        lay.addWidget(label(title, T.TEXT, 20, bold=True))
        lay.addSpacing(5)
        sub_lbl = QLabel(sub); sub_lbl.setWordWrap(True)
        f = QFont(T.FONT_FAMILY); f.setPixelSize(12); sub_lbl.setFont(f)
        sub_lbl.setStyleSheet(f"color:{T.TEXT_MUTED};background:transparent;")
        lay.addWidget(sub_lbl)
        lay.addSpacing(20)
        content = QVBoxLayout(); content.setSpacing(8)
        lay.addLayout(content, 1)
        lay.addSpacing(14)
        return w, lay, content

    # ── pages ──────────────────────────────────────────────────────────── #
    def _p_welcome(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(52, 56, 52, 40); lay.setSpacing(0)
        lay.addStretch(1)
        lay.addWidget(label("$", T.ACCENT, 42, bold=True,
                            align=Qt.AlignmentFlag.AlignCenter))
        lay.addSpacing(16)
        lay.addWidget(label("Welcome to Budget", T.TEXT, 24, bold=True,
                            align=Qt.AlignmentFlag.AlignCenter))
        lay.addSpacing(10)
        sub = QLabel("Your personal finance tracker.\n"
                     "Simple, private — everything stays on your device.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sub.setWordWrap(True)
        f = QFont(T.FONT_FAMILY); f.setPixelSize(13); sub.setFont(f)
        sub.setStyleSheet(f"color:{T.TEXT_MUTED};background:transparent;")
        lay.addWidget(sub)
        lay.addStretch(2)
        btn = self._btn("Get started →", primary=True)
        btn.setFixedHeight(42); btn.clicked.connect(lambda: self._go(1))
        lay.addWidget(btn)
        return w

    _UNIT_LABELS = ["days", "weeks", "months", "years"]
    _UNIT_KEYS   = ["day",  "week",  "month",  "year"]

    def _col_header_row(self, specs):
        """specs = [(label, stretch_or_width), ...]  width<0 means stretch."""
        row = QHBoxLayout(); row.setSpacing(7); row.setContentsMargins(0, 0, 22, 0)
        for lbl_text, w in specs:
            lbl = label(lbl_text, T.TEXT_DIM, 10)
            if w < 0:
                row.addWidget(lbl, 1)
            else:
                lbl.setFixedWidth(w)
                row.addWidget(lbl)
        return row

    @staticmethod
    def _amount_edit(width: int) -> QLineEdit:
        """Amount field that only accepts digits, commas and a decimal point."""
        from PyQt6.QtCore import QRegularExpression
        from PyQt6.QtGui import QRegularExpressionValidator
        le = QLineEdit(); le.setPlaceholderText("0.00"); le.setFixedWidth(width)
        le.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9,.\s]*")))
        return le

    def _recur_widgets(self, default_n=1, default_unit=2):
        """Return (n_spin, unit_combo) pre-configured. default_unit: 2=months."""
        n_spin = QSpinBox(); n_spin.setRange(1, 999); n_spin.setValue(default_n)
        n_spin.setFixedWidth(52)
        unit_cb = QComboBox(); unit_cb.addItems(self._UNIT_LABELS)
        unit_cb.setCurrentIndex(default_unit); unit_cb.setFixedWidth(80)
        return n_spin, unit_cb

    def _p_income(self):
        w, lay, content = self._shell(1, "Income sources",
                                       "Add each income source, the amount per payment, "
                                       "and how often you receive it.")
        content.addLayout(self._col_header_row([
            ("Source", -1), ("Amount", 80), ("Every", 52), ("", 80)]))
        scroll_w = QWidget(); scroll_w.setStyleSheet("background:transparent;")
        self._income_box = QVBoxLayout(scroll_w)
        self._income_box.setContentsMargins(0, 0, 0, 0); self._income_box.setSpacing(6)
        sc = BoundedScroll(); sc.setWidgetResizable(True)
        sc.setStyleSheet("background:transparent;border:none;"); sc.setWidget(scroll_w)
        content.addWidget(sc, 1)
        add = Clickable("+ Add source", T.TEXT_MUTED, 12, hover=T.ACCENT)
        add.clicked.connect(self._add_income_pair)
        content.addWidget(add)
        lay.addLayout(self._nav_row(back_idx=0, next_fn=lambda: self._go(2),
                                    skip_fn=lambda: self._go(2)))
        self._add_income_pair()
        return w

    def _add_income_pair(self):
        row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
        rl = QHBoxLayout(row_w)
        rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(7)
        name_le = QLineEdit(); name_le.setPlaceholderText("e.g. Salary")
        amt_le  = self._amount_edit(80)
        n_spin, unit_cb = self._recur_widgets(1, 2)  # default: every 1 month
        pair = (name_le, amt_le, n_spin, unit_cb)
        self._income_pairs.append(pair)

        def remove():
            if pair in self._income_pairs:
                self._income_pairs.remove(pair)
            self._income_box.removeWidget(row_w); row_w.deleteLater()

        rm = Clickable("✕", T.TEXT_DIM, 11, hover=T.RED)
        rm.clicked.connect(remove)
        rl.addWidget(name_le, 1); rl.addWidget(amt_le)
        rl.addWidget(n_spin); rl.addWidget(unit_cb); rl.addWidget(rm)
        self._income_box.addWidget(row_w)
        name_le.setFocus()

    def _p_expenses(self):
        w, lay, content = self._shell(2, "Regular expenses",
                                       "Add recurring bills — rent, utilities, subscriptions…"
                                       " Pick the due date and how often it recurs.")
        content.addLayout(self._col_header_row([
            ("Expense", -1), ("Amount", 76), ("Due date", 100), ("Every", 52), ("", 80)]))
        scroll_w = QWidget(); scroll_w.setStyleSheet("background:transparent;")
        self._expense_box = QVBoxLayout(scroll_w)
        self._expense_box.setContentsMargins(0, 0, 0, 0); self._expense_box.setSpacing(6)
        sc = BoundedScroll(); sc.setWidgetResizable(True)
        sc.setStyleSheet("background:transparent;border:none;"); sc.setWidget(scroll_w)
        content.addWidget(sc, 1)
        add = Clickable("+ Add expense", T.TEXT_MUTED, 12, hover=T.ACCENT)
        add.clicked.connect(self._add_expense_pair)
        content.addWidget(add)
        lay.addLayout(self._nav_row(back_idx=1, next_fn=lambda: self._go(3),
                                    skip_fn=lambda: self._go(3)))
        self._add_expense_pair()
        return w

    def _add_expense_pair(self):
        row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
        rl = QHBoxLayout(row_w)
        rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(7)
        name_le = QLineEdit(); name_le.setPlaceholderText("e.g. Rent")
        amt_le  = self._amount_edit(76)
        due_de  = QDateEdit()
        due_de.setCalendarPopup(True)
        due_de.setDate(QDate(self.today.year, self.today.month, 1))
        due_de.setDisplayFormat("dd/MM/yyyy"); due_de.setFixedWidth(100)
        due_de.dateChanged.connect(lambda _: due_de.lineEdit().deselect())
        n_spin, unit_cb = self._recur_widgets(1, 2)  # default: every 1 month
        pair = (name_le, amt_le, due_de, n_spin, unit_cb)
        self._expense_pairs.append(pair)

        def remove():
            if pair in self._expense_pairs:
                self._expense_pairs.remove(pair)
            self._expense_box.removeWidget(row_w); row_w.deleteLater()

        rm = Clickable("✕", T.TEXT_DIM, 11, hover=T.RED)
        rm.clicked.connect(remove)
        rl.addWidget(name_le, 1); rl.addWidget(amt_le); rl.addWidget(due_de)
        rl.addWidget(n_spin); rl.addWidget(unit_cb); rl.addWidget(rm)
        self._expense_box.addWidget(row_w)
        name_le.setFocus()

    def _p_targets(self):
        w, lay, content = self._shell(3, "Monthly savings target",
                                       "How much do you want to save each month? "
                                       "You can update this any time in Settings.")
        content.addWidget(label("Target monthly savings", T.TEXT_MUTED, 11))
        self._tgt_le = QLineEdit(); self._tgt_le.setPlaceholderText("e.g. 500")
        from PyQt6.QtCore import QRegularExpression
        from PyQt6.QtGui import QRegularExpressionValidator
        self._tgt_le.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[0-9,.\s]*")))
        content.addWidget(self._tgt_le)
        content.addStretch(1)
        lay.addLayout(self._nav_row(back_idx=2, next_fn=self._commit_targets,
                                    next_text="Finish →"))
        return w

    def _commit_targets(self):
        raw = self._tgt_le.text().replace(",", "").strip()
        try:
            self._target_pnl = float(raw or "0")
        except ValueError:
            from PyQt6.QtWidgets import QToolTip
            self._tgt_le.setFocus()
            QToolTip.showText(
                self._tgt_le.mapToGlobal(self._tgt_le.rect().bottomLeft()),
                f"Couldn't read \"{raw}\" as a number.", self._tgt_le)
            return
        self._build_result()
        self._go(4)

    def _build_result(self):
        def pf(le):
            try: return float(le.text().replace(",", "").strip() or "0")
            except ValueError: return 0.0
        added = self.today.strftime("%m-%d")
        doc = {
            "month":         dm.month_key(self.today.year, self.today.month),
            "income":        [],
            "expenses":      [],
            "target_pnl":    getattr(self, "_target_pnl", 0.0),
            "weekly_budget": 0.0,
            "weeks":         4,
            "currency":      "$",
        }
        for name_le, amt_le, n_spin, unit_cb in self._income_pairs:
            n = name_le.text().strip()
            if not n: continue
            repeat = {"type": "interval",
                      "every": n_spin.value(),
                      "unit": self._UNIT_KEYS[unit_cb.currentIndex()]}
            doc["income"].append(dm.cat(n, pf(amt_le), repeat=repeat, added=added))
        for name_le, amt_le, due_de, n_spin, unit_cb in self._expense_pairs:
            n = name_le.text().strip()
            if not n: continue
            repeat = {"type": "interval",
                      "every": n_spin.value(),
                      "unit": self._UNIT_KEYS[unit_cb.currentIndex()]}
            qd = due_de.date()
            due = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
            doc["expenses"].append(
                dm.cat(n, pf(amt_le), type="expense", repeat=repeat, due=due, added=added))
        self.result_doc = doc

    def _p_done(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(52, 56, 52, 40); lay.setSpacing(0)
        lay.addStretch(1)
        lay.addWidget(label("✓", T.ACCENT, 38, bold=True,
                            align=Qt.AlignmentFlag.AlignCenter))
        lay.addSpacing(14)
        lay.addWidget(label("You're all set!", T.TEXT, 22, bold=True,
                            align=Qt.AlignmentFlag.AlignCenter))
        lay.addSpacing(10)
        sub = QLabel("Your budget is ready.\nAdd or edit items any time from the Overview.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sub.setWordWrap(True)
        f = QFont(T.FONT_FAMILY); f.setPixelSize(13); sub.setFont(f)
        sub.setStyleSheet(f"color:{T.TEXT_MUTED};background:transparent;")
        lay.addWidget(sub)
        lay.addStretch(2)
        btn = self._btn("Open dashboard →", primary=True)
        btn.setFixedHeight(42); btn.clicked.connect(self.accept)
        lay.addWidget(btn)
        return w


# --------------------------------------------------------------------------- #
#  Subscriptions page — full subscription + people manager
# --------------------------------------------------------------------------- #
class SubscriptionsPage(QWidget):
    """Full subscription manager — every subscription (solo / split / income)
    and the people on them."""

    def __init__(self, manager, doc, year, month, on_change):
        super().__init__()
        self.dm, self.on_change = manager, on_change
        self.year, self.month = year, month
        self.currency = doc.get("currency", "$")
        self.view = "Subscriptions"

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        tabhost = QWidget()
        tabhost.setStyleSheet(
            f"background:{T.BG_CARD}; border-bottom:1px solid {T.BORDER_SOFT};")
        tl = QHBoxLayout(tabhost); tl.setContentsMargins(20, 0, 20, 0)
        self.tabbar = SegTabBar(["Subscriptions", "People"], 0, kind="tab")
        self.tabbar.changed.connect(self._switch)
        tl.addWidget(self.tabbar); tl.addStretch(1)
        self.add_btn = _button("+ Add subscription", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        self.add_btn.clicked.connect(self._add_subscription)
        tl.addWidget(self.add_btn)
        outer.addWidget(tabhost)

        self.body = QWidget()
        self.blay = QVBoxLayout(self.body)
        self.blay.setContentsMargins(20, 16, 20, 18); self.blay.setSpacing(14)
        outer.addWidget(scrollable(self.body))

    def _month_range(self):
        import calendar as _c
        last = _c.monthrange(self.year, self.month)[1]
        return date(self.year, self.month, 1), date(self.year, self.month, last)

    def _occ_in_month(self, defn):
        rs, re_ = self._month_range()
        occs = B.occurrence_dates(defn, rs, re_)
        return occs[0] if occs else None

    def _switch(self, name):
        self.view = name
        self.add_btn.setVisible(name == "Subscriptions")
        self._rebuild()

    def set_context(self, doc, year, month):
        self.year, self.month = year, month
        self.currency = doc.get("currency", "$")
        self.add_btn.setVisible(self.view == "Subscriptions")
        self._rebuild()

    def _rebuild(self):
        clear_layout(self.blay)
        (self._build_subscriptions if self.view == "Subscriptions"
         else self._build_people)()
        self.blay.addStretch(1)

    # -- subscriptions list ----------------------------------------------- #
    def _build_subscriptions(self):
        cur = self.currency
        rs, re_ = self._month_range()
        subs = self.dm.all_subscriptions()

        owed = sum(o["owes"] for o in B.who_owes(self.dm.items(), rs, re_))
        monthly = 0.0
        for d in subs:
            occ = self._occ_in_month(d)
            if d.get("shared") and d.get("type") == "expense" and occ:
                monthly += B.plan_summary(d, occ)["your_net"]
            elif not d.get("shared"):
                monthly += B.monthly_equiv(d.get("amount", 0), d.get("recurrence"))

        trow, tiles = tile_row(["Subscriptions", "Your monthly cost", "Owed to you"])
        tiles[0].set_value(str(len(subs)))
        tiles[1].set_value(money(monthly, cur, signed=False, cents=True))
        tiles[2].set_value(money(owed, cur, signed=False, cents=True),
                           T.AMBER if owed > 0 else T.GREEN)
        self.blay.addLayout(trow)

        # month calendar — daily spend shading + due / income dots
        hm_card, hml = card()
        hml.addWidget(label(
            f"Spending & due dates — {dm.MONTH_NAMES[self.month]} {self.year}",
            T.TEXT_MUTED, 12))
        heatmap = CalendarHeatmap()
        spend = B.daily_spend(self.dm.transactions(), self.year, self.month)
        due_days: dict[int, list[str]] = {}
        income_days: set[int] = set()
        for inst in B.instances_in_range(self.dm.items(), rs, re_):
            day = inst["occ_date"].day
            if inst["type"] == "income":
                income_days.add(day)
            elif not inst.get("paid"):
                due_days.setdefault(day, []).append(inst["name"])
        heatmap.set_month(self.year, self.month, spend, due_days,
                          income_days, today=date.today(), currency=cur)
        hml.addWidget(heatmap)
        self.blay.addWidget(hm_card)

        # renewal timeline — next 60 days
        upcoming = B.upcoming_renewals(self.dm.items(), date.today(), days=60)
        if upcoming:
            tl_card, tll = card()
            tll.addWidget(label("Renewal timeline — next 60 days", T.TEXT_MUTED, 12))
            timeline = SubscriptionTimeline()
            timeline.set_data(upcoming, days=60, currency=cur)
            tll.addWidget(timeline)
            self.blay.addWidget(tl_card)

        # B1 — renewing soon
        renewals = B.upcoming_renewals(self.dm.items(), date.today(), days=14)
        if renewals:
            rc, rl = card()
            tot = sum(r["amount"] for r in renewals if r["type"] == "expense")
            rl.addWidget(label(
                f"Renewing in the next 14 days  ·  {money(tot, cur, signed=False, cents=True)}",
                T.TEXT, 13, bold=True))
            for r in renewals:
                d = date.fromisoformat(r["next"])
                when = "today" if r["days_until"] == 0 else f"in {r['days_until']}d"
                row = QHBoxLayout(); row.setSpacing(8)
                row.addWidget(label(r["name"], T.TEXT, 12))
                row.addWidget(label(f"{d.strftime('%d %b')} · {when}",
                                    T.AMBER if r["days_until"] <= 3 else T.TEXT_DIM, 11))
                row.addStretch(1)
                row.addWidget(label(money(r["amount"], cur, signed=False, cents=True),
                                    T.GREEN if r["type"] == "income" else T.RED, 12, bold=True))
                rl.addLayout(row)
            self.blay.addWidget(rc)

        if subs:
            # B5 — rank by annualised cost (biggest first)
            subs = sorted(subs, key=lambda d: -B.monthly_equiv(
                d.get("amount", 0), d.get("recurrence")))
            for defn in subs:
                self.blay.addWidget(self._plan_card(defn, cur) if defn.get("shared")
                                    else self._solo_card(defn, cur))
        else:
            self.blay.addWidget(label(
                "No subscriptions yet — use “+ Add subscription” to add one you pay, "
                "one you split with people, or a client deal others pay you for.",
                T.TEXT_DIM, 12))

        self._forgotten_section(cur)

    def _forgotten_section(self, cur):
        detected = [d for d in B.detect_subscriptions(self.dm.transactions())
                    if d["direction"] == "outgoing"]
        tracked = [d.get("name", "").lower() for d in self.dm.all_subscriptions()]
        forgotten = [d for d in detected if not any(
            d["merchant"].lower() in t or t in d["merchant"].lower()
            for t in tracked if t)]
        if not forgotten:
            return
        dc, dl = card()
        dl.addWidget(label("Might've forgotten — recurring in your bank, not tracked",
                           T.TEXT, 13, bold=True))
        for d in forgotten:
            row = QHBoxLayout(); row.setSpacing(8)
            row.addWidget(label(d["merchant"], T.TEXT, 12))
            row.addWidget(label(f"×{d['count']}", T.TEXT_DIM, 10))
            row.addStretch(1)
            row.addWidget(label(f"~{money(d['avg_amount'], cur, signed=False, cents=True)}",
                                T.TEXT_MUTED, 12))
            addb = _button("+ Track", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
            addb.clicked.connect(lambda _=False, nm=d["merchant"], a=d["avg_amount"]:
                                 self._track_forgotten(nm, a))
            row.addWidget(addb)
            dl.addLayout(row)
        self.blay.addWidget(dc)

    def _track_forgotten(self, name, amount):
        start = f"{self.year:04d}-{self.month:02d}-01"
        self.dm.create_subscription(name, amount, start, None)
        self.on_change()

    # -- free-trial / cancel-by (B2) -------------------------------------- #
    def _cancel_badge(self, defn):
        cb = defn.get("cancel_by")
        if not cb:
            return None
        try:
            d = date.fromisoformat(cb)
        except ValueError:
            return None
        days = (d - date.today()).days
        if days < 0:
            return label(f"⚠ cancel-by passed {d.strftime('%d %b')}", T.RED, 11, bold=True)
        if days <= 7:
            return label(f"cancel by {d.strftime('%d %b')} ({days}d)", T.AMBER, 11, bold=True)
        return label(f"cancel by {d.strftime('%d %b')}", T.TEXT_DIM, 11)

    def _pick_cancel_by(self, defn):
        from PyQt6.QtWidgets import QMenu, QWidgetAction, QCalendarWidget
        m = QMenu(self)
        cal = QCalendarWidget(); cal.setFixedSize(266, 200)
        if defn.get("cancel_by"):
            cal.setSelectedDate(QDate.fromString(defn["cancel_by"], "yyyy-MM-dd"))
        cal.clicked.connect(lambda qd: self._set_cancel_by(
            defn["id"], qd.toString("yyyy-MM-dd"), m))
        wa = QWidgetAction(m); wa.setDefaultWidget(cal); m.addAction(wa)
        if defn.get("cancel_by"):
            m.addSeparator()
            m.addAction("Clear", lambda: self._set_cancel_by(defn["id"], None, m))
        m.exec(QCursor.pos())

    def _set_cancel_by(self, def_id, iso, menu):
        self.dm.set_cancel_by(def_id, iso)
        menu.close()
        self.on_change()

    def _solo_card(self, defn, cur):
        c, cl = card()
        head = QHBoxLayout(); head.setSpacing(8)
        head.addWidget(label(defn["name"], T.TEXT, 15, bold=True))
        head.addWidget(label(
            f"· {money(defn.get('amount', 0), cur, signed=False, cents=True)} · "
            f"{repeat_label(defn.get('recurrence')) or 'monthly'} · just me",
            T.TEXT_MUTED, 11))
        head.addStretch(1)
        nxt = B.next_occurrence(defn, date.today())
        if nxt:
            head.addWidget(label(f"next {nxt.strftime('%d %b %Y')}", T.TEXT_DIM, 11))
        for t in (defn.get("tags") or [])[:3]:
            head.addWidget(tag_chip(t))
        bdg = self._cancel_badge(defn)
        if bdg:
            head.addWidget(bdg)
        cbtn = Clickable("⏰", T.TEXT_DIM, 12, hover=T.AMBER)
        cbtn.setToolTip("Set free-trial / cancel-by date")
        cbtn.clicked.connect(lambda _=False, d=defn: self._pick_cancel_by(d))
        head.addWidget(cbtn)
        ebtn = Clickable("✎", T.TEXT_DIM, 12, hover=T.ACCENT)
        ebtn.setToolTip("Edit subscription")
        ebtn.clicked.connect(lambda _=False, d=defn: self._edit_subscription(d))
        head.addWidget(ebtn)
        delb = Clickable("✕", T.TEXT_DIM, 12, hover=T.RED)
        delb.setToolTip("Delete subscription")
        delb.clicked.connect(lambda _=False, d=defn["id"]: self._delete(d))
        head.addWidget(delb)
        cl.addLayout(head)
        return c

    def _plan_card(self, defn, cur):
        c, cl = card()
        occ = self._occ_in_month(defn)
        is_expense = defn.get("type") == "expense"

        head = QHBoxLayout(); head.setSpacing(8)
        head.addWidget(label(defn["name"], T.TEXT, 15, bold=True))
        kind = "I pay & split" if is_expense else "they pay me"
        gross = defn.get('amount', 0)
        if is_expense and occ:
            # P&L-relevant net cost first; raw bank charge in brackets
            net = B.plan_summary(defn, occ)["your_net"]
            amt = (f"{money(net, cur, signed=False, cents=True)} "
                   f"({money(gross, cur, signed=False, cents=True)})")
        else:
            amt = money(gross, cur, signed=False, cents=True)
        head.addWidget(label(
            f"· {amt} · "
            f"{repeat_label(defn.get('recurrence')) or 'monthly'} · {kind}",
            T.TEXT_MUTED, 11))
        head.addStretch(1)
        if occ:
            s = B.plan_summary(defn, occ)
            if s["ready"]:
                txt = "✓ All settled" if is_expense else "✓ Ready to ship — all paid"
                head.addWidget(label(txt, T.GREEN, 11, bold=True))
            else:
                head.addWidget(label("Waiting on " + ", ".join(s["unpaid"]),
                                     T.AMBER, 11, bold=True))
        bdg = self._cancel_badge(defn)
        if bdg:
            head.addWidget(bdg)
        cbtn = Clickable("⏰", T.TEXT_DIM, 12, hover=T.AMBER)
        cbtn.setToolTip("Set free-trial / cancel-by date")
        cbtn.clicked.connect(lambda _=False, d=defn: self._pick_cancel_by(d))
        head.addWidget(cbtn)
        ebtn = Clickable("✎", T.TEXT_DIM, 12, hover=T.ACCENT)
        ebtn.setToolTip("Edit subscription")
        ebtn.clicked.connect(lambda _=False, d=defn: self._edit_subscription(d))
        head.addWidget(ebtn)
        delb = Clickable("✕", T.TEXT_DIM, 12, hover=T.RED)
        delb.setToolTip("Delete subscription")
        delb.clicked.connect(lambda _=False, d=defn["id"]: self._delete(d))
        head.addWidget(delb)
        cl.addLayout(head)

        if occ:
            s = B.plan_summary(defn, occ)
            if is_expense:
                metrics = (f"Your net cost {money(s['your_net'], cur, signed=False, cents=True)}  ·  "
                           f"recovered {money(s['recovered'], cur, signed=False, cents=True)} of "
                           f"{money(s['member_total'], cur, signed=False, cents=True)}  ·  "
                           f"{money(s['outstanding'], cur, signed=False, cents=True)} still owed to you")
            else:
                metrics = (f"Collected {money(s['recovered'], cur, signed=False, cents=True)} of "
                           f"{money(s['total'], cur, signed=False, cents=True)}  ·  "
                           f"{money(s['outstanding'], cur, signed=False, cents=True)} outstanding")
            cl.addWidget(label(metrics, T.TEXT_DIM, 11))
        cl.addWidget(hsep())

        if not occ:
            cl.addWidget(label("No payment cycle in this month.", T.TEXT_DIM, 11))
            return c
        for r in B.member_shares(defn, occ):
            mr = QHBoxLayout(); mr.setSpacing(8)
            mr.addWidget(label(r["name"], T.TEXT, 12))
            mr.addStretch(1)
            mr.addWidget(label(money(r["share"], cur, signed=False, cents=True), T.TEXT_MUTED, 12))
            paid = r["paid"]
            btn = _button("Paid ✓" if paid else "Mark paid",
                          T.GREEN if paid else T.TEXT_MUTED,
                          T.GREEN_BG if paid else T.BG_INPUT,
                          T.GREEN_BORDER if paid else T.BORDER)
            btn.clicked.connect(
                lambda _=False, d=defn["id"], o=occ.isoformat(),
                nm=r["name"], pv=not paid: self._toggle_paid(d, o, nm, pv))
            mr.addWidget(btn)
            cl.addLayout(mr)
        return c

    def _toggle_paid(self, def_id, occ_iso, member, paid):
        self.dm.set_member_paid(def_id, occ_iso, member, paid)
        self.on_change()

    def _delete(self, def_id):
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Delete", "Delete this subscription?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.dm.delete_def(def_id)
            self.on_change()

    def _add_subscription(self):
        res = SharedPlanDialog.create(self, self.currency)
        if not res:
            return
        start = res.get("start") or f"{self.year:04d}-{self.month:02d}-01"
        if res.get("solo"):
            self.dm.create_subscription(res["name"], res["amount"], start,
                                        res["recurrence"])
        else:
            self.dm.create_shared_plan(res["name"], res["amount"], res["type"],
                                       start, res["shared"], res["recurrence"])
        self.on_change()

    def _edit_subscription(self, defn):
        res = SharedPlanDialog.edit(self, defn, self.currency)
        if not res:
            return
        if res.get("solo"):
            self.dm.update_subscription(
                defn["id"], name=res["name"], amount=res["amount"],
                item_type="expense", recurrence=res["recurrence"], shared=None,
                start=res.get("start"))
        else:
            self.dm.update_subscription(
                defn["id"], name=res["name"], amount=res["amount"],
                item_type=res["type"], recurrence=res["recurrence"],
                shared=res["shared"], start=res.get("start"))
        self.on_change()

    # -- people: registry + per-person subscription selection ------------- #
    def _add_person(self):
        res = PersonDialog.create(self)
        if res:
            self.dm.add_person(res["name"], email=res["email"],
                               phone=res["phone"], note=res["note"])
            self.on_change()

    def _edit_person(self, pid):
        person = next((p for p in self.dm.people() if p.get("id") == pid), None)
        if not person:
            return
        res = PersonDialog.edit(self, person)
        if res:
            self.dm.update_person(pid, **res)
            self.on_change()

    def _remove_person(self, pid):
        from PyQt6.QtWidgets import QMessageBox
        person = next((p for p in self.dm.people() if p.get("id") == pid), None)
        name = person.get("name", "this person") if person else "this person"
        if QMessageBox.question(
                self, "Remove person",
                f"Remove {name}? They will be dropped from every shared plan.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.dm.remove_person(pid)
        self.on_change()

    def _set_person_sub(self, name, sub_id, member):
        self.dm.set_person_in_sub(name, sub_id, member)
        self.on_change()

    def _settle_up(self, name):
        """Mark a person paid across every subscription they owe on this cycle."""
        rs, re_ = self._month_range()
        for o in B.people_roster(self.dm.items(), rs, re_):
            if o["member"] != name:
                continue
            for pl in o["plans"]:
                if not pl["paid"]:
                    self.dm.set_member_paid(pl["id"], pl["date"], name, True)
        self.on_change()

    def _copy_reminder(self, name, info):
        from PyQt6.QtWidgets import QApplication
        if not info or info["owes"] <= 1e-9:
            return
        cur = self.currency
        parts = [f"{pl['name']} {money(pl['share'], cur, signed=False, cents=True)}"
                 for pl in info["plans"] if not pl["paid"]]
        msg = (f"Hi {name}, you owe {money(info['owes'], cur, signed=False, cents=True)} "
               f"({', '.join(parts)}). Thanks!")
        QApplication.clipboard().setText(msg)
        if hasattr(self, "_people_status"):
            self._people_status.setText(f"✓ Copied {name}'s reminder to the clipboard.")

    def _build_people(self):
        cur = self.currency
        rs, re_ = self._month_range()
        people = self.dm.people()
        roster = {p["member"]: p for p in B.people_roster(self.dm.items(), rs, re_)}
        shared_subs = self.dm.shared_plans()

        self.blay.addWidget(label(
            "Add people and tick which subscriptions they're on — their share is "
            "worked out automatically.", T.TEXT_MUTED, 11))

        ac, al = card()
        arow = QHBoxLayout(); arow.setSpacing(8)
        arow.addWidget(label("Keep contact details with each payee so "
                             "reminders and settle-ups are one click away.",
                             T.TEXT_DIM, 11))
        arow.addStretch(1)
        addb = _button("+ Add person", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
        addb.clicked.connect(self._add_person)
        arow.addWidget(addb)
        al.addLayout(arow)
        self.blay.addWidget(ac)
        self._people_status = label("", T.GREEN, 11)
        self.blay.addWidget(self._people_status)

        if not people:
            self.blay.addWidget(label(
                "No people yet — add someone above, or create a split subscription.",
                T.TEXT_DIM, 12))
            return

        total_owed = sum(p["owes"] for p in roster.values())
        trow, tiles = tile_row(["People", "Owed to you"])
        tiles[0].set_value(str(len(people)))
        tiles[1].set_value(money(total_owed, cur, signed=False, cents=True),
                           T.AMBER if total_owed > 0 else T.GREEN)
        self.blay.addLayout(trow)

        # who-owes-what signed bars (green owed to you, red you owe)
        owe_rows = [(p["name"], roster[p["name"]]["owes"])
                    for p in people if p["name"] in roster
                    and abs(roster[p["name"]]["owes"]) > 0.001]
        if owe_rows:
            wc, wl = card()
            wl.addWidget(label("Balances — who owes what", T.TEXT_MUTED, 12))
            bar = WhoOwesBar()
            bar.set_data(sorted(owe_rows, key=lambda r: -r[1]), cur)
            wl.addWidget(bar)
            self.blay.addWidget(wc)

        for person in people:
            name = person["name"]
            info = roster.get(name)
            owes = info["owes"] if info else 0.0
            total = info["total"] if info else 0.0
            plan_info = {pl["name"]: pl for pl in (info["plans"] if info else [])}
            in_subs = self.dm.person_in_subs(name)

            c, cl = card()
            head = QHBoxLayout(); head.setSpacing(8)
            head.addWidget(label(name, T.TEXT, 15, bold=True))
            head.addStretch(1)
            settled = owes <= 1e-9
            head.addWidget(label(
                "all settled" if settled else f"owes {money(owes, cur, signed=False, cents=True)}",
                T.GREEN if settled else T.AMBER, 12, bold=True))
            head.addWidget(label(f"of {money(total, cur, signed=False, cents=True)}", T.TEXT_DIM, 10))
            if not settled:
                stl = _button("Settle up", T.GREEN, T.GREEN_BG, T.GREEN_BORDER)
                stl.clicked.connect(lambda _=False, nm=name: self._settle_up(nm))
                head.addWidget(stl)
                cpy = _button("Copy reminder", T.TEXT_MUTED, T.BG_INPUT, T.BORDER)
                cpy.clicked.connect(lambda _=False, nm=name, inf=info:
                                    self._copy_reminder(nm, inf))
                head.addWidget(cpy)
            ed = Clickable("✎", T.TEXT_DIM, 12, hover=T.TEXT)
            ed.setToolTip("Edit contact details")
            ed.clicked.connect(lambda _=False, pid=person["id"]: self._edit_person(pid))
            head.addWidget(ed)
            rm = Clickable("✕", T.TEXT_DIM, 12, hover=T.RED)
            rm.setToolTip("Remove person")
            rm.clicked.connect(lambda _=False, pid=person["id"]: self._remove_person(pid))
            head.addWidget(rm)
            cl.addLayout(head)
            contact = "  ·  ".join(x for x in (person.get("email"),
                                               person.get("phone"),
                                               person.get("note")) if x)
            if contact:
                cl.addWidget(label(contact, T.TEXT_DIM, 10))
            cl.addWidget(hsep())

            if not shared_subs:
                cl.addWidget(label("No shared subscriptions to assign yet.",
                                   T.TEXT_DIM, 11))
            for sub in shared_subs:
                r = QHBoxLayout(); r.setSpacing(8)
                cb = QCheckBox(sub["name"])
                cb.setChecked(sub["id"] in in_subs)
                cb.setCursor(Qt.CursorShape.PointingHandCursor)
                cb.setStyleSheet(f"color:{T.TEXT};")
                cb.toggled.connect(lambda vis, nm=name, sid=sub["id"]:
                                   self._set_person_sub(nm, sid, vis))
                r.addWidget(cb)
                r.addStretch(1)
                pl = plan_info.get(sub["name"])
                if pl:
                    r.addWidget(label(money(pl["share"], cur, signed=False, cents=True),
                                      T.TEXT_MUTED, 12))
                    paid = pl["paid"]
                    btn = _button("Paid ✓" if paid else "Mark paid",
                                  T.GREEN if paid else T.TEXT_MUTED,
                                  T.GREEN_BG if paid else T.BG_INPUT,
                                  T.GREEN_BORDER if paid else T.BORDER)
                    btn.clicked.connect(
                        lambda _=False, d=sub["id"], o=pl["date"],
                        n2=name, pv=not paid: self._toggle_paid(d, o, n2, pv))
                    r.addWidget(btn)
                cl.addLayout(r)
            self.blay.addWidget(c)



# --------------------------------------------------------------------------- #
#  Main window
# --------------------------------------------------------------------------- #
TITLES = {"overview": "Overview", "income": "Income", "expenses": "Expenses",
          "analytics": "Analytics", "subscriptions": "Subscriptions",
          "goals": "Goals", "history": "History",
          "settings": "Settings"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Budget")
        self.resize(T.WIN_W, T.WIN_H)
        self.setMinimumSize(1160, 720)

        self.dm = dm.ItemStore()
        self.dm.load()                       # migrate month files → flat store on first run
        self.today = date.today()
        self.dm.snapshot_net_worth(self.today)   # record daily net-worth point
        self._first_run = False              # store seeds itself; onboarding deferred
        self.anchor = self.today             # the date whose lens-window is shown
        self.lens = self.dm.time_lens()      # "iso_week" (default) | "monday_in_month" | "month"
        self._week_style = self.dm.settings().get("week_style", "iso_week")
        self.year, self.month = self.anchor.year, self.anchor.month
        rs, re_, lab = B.range_for_lens(self.lens, self.anchor)
        self.doc = self.dm.load_range(rs, re_, lab)

        root = QWidget(); root.setObjectName("Root")
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigated.connect(self.go)
        h.addWidget(self.sidebar)

        right = QWidget()
        rlay = QVBoxLayout(right); rlay.setContentsMargins(0, 0, 0, 0); rlay.setSpacing(0)
        self.topbar = TopBar()
        self.topbar.prev.connect(lambda: self.shift_period(-1))
        self.topbar.next.connect(lambda: self.shift_period(1))
        self.topbar.today.connect(self._goto_today)
        self.topbar.jump.connect(self.goto_month)
        self.topbar.search.connect(self._open_search)
        self.topbar.mode_changed.connect(self.set_mode)
        self.topbar.edit_changed.connect(self._set_edit_mode)
        rlay.addWidget(self.topbar)

        self.stack = QStackedWidget()
        rlay.addWidget(self.stack, 1)
        h.addWidget(right, 1)
        self.setCentralWidget(root)

        ch = self._data_changed
        self.overview  = OverviewPage(self.dm, self.doc, self.year, self.month,
                                      self.today, ch)
        self.analytics = AnalyticsPage(self.dm, self.doc, self.year, self.month, ch)
        self.subs      = SubscriptionsPage(self.dm, self.doc, self.year, self.month, ch)
        self.goals     = GoalsPage(self.dm, self.doc, self.year, self.month, ch)
        self.history   = HistoryPage(self.dm, self.goto_month)
        self.settings  = SettingsPage(self.dm, ch)

        self.pages = {"overview":      self.overview,
                      "analytics":     self.analytics,
                      "subscriptions": self.subs,
                      "goals":         self.goals,
                      "history":       self.history,
                      "settings":      self.settings}
        for p in self.pages.values():
            self.stack.addWidget(p)

        for _c in (self.analytics._inc.card, self.analytics._exp.card):
            _c.store = self.dm                 # analytics ledgers persist to the store too
        for _c in (self.overview.income_card, self.overview.expense_card,
                   self.analytics._inc.card, self.analytics._exp.card):
            _c.delete_recurring.connect(self._delete_recurring)   # legacy path (unused under store)
        self.settings.reset_requested.connect(self._reset_all_data)
        self.settings.week_style_changed.connect(self._set_week_style)
        self.settings.sidebar_changed.connect(self._apply_sidebar)
        self.analytics.navigate_to.connect(self._goto_month_overview)

        self._load_user_modules()        # discover & mount data/modules/*.py
        self._apply_sidebar()

        # reflect the active lens on the Month|Week pill, then apply it
        self.topbar.set_mode("month" if self.lens == "month" else "week")
        self._load_anchor()
        self.go("overview")

    def _load_user_modules(self):
        """Discover and mount user modules from data/modules/ (errors isolated)."""
        import modules as _mods
        helpers = {
            "card": card, "tile_row": tile_row, "scrollable": scrollable,
            "label": label, "money": money, "clear_layout": clear_layout,
            "hsep": hsep, "tag_chip": tag_chip, "ProgressBar": ProgressBar,
            "LineChart": LineChart, "Clickable": Clickable,
        }
        api = _mods.ModuleAPI(self.dm, B, T, helpers, navigate=self.go)
        self._module_loaded, self._module_errors = _mods.load_modules(api)
        self._module_keys = []
        for mp in api.pages:
            key = "mod:" + mp["key"]
            if key in self.pages:
                continue
            self.pages[key] = mp["widget"]
            self.stack.addWidget(mp["widget"])
            TITLES[key] = mp["title"]
            self._NAV_VIS[key] = (False, False)
            self.sidebar.add_module_nav(key, mp["icon"], mp["title"][:9])
            self._module_keys.append(key)
        self.settings.set_module_info(self._module_loaded, self._module_errors,
                                      _mods.modules_dir())

    def _set_edit_mode(self, on: bool):
        """Propagate global edit mode to every ledger card in the app."""
        for card in (self.overview.income_card, self.overview.expense_card,
                     self.analytics._inc.card, self.analytics._exp.card):
            card.set_edit_mode(on)

    # -- navigation ------------------------------------------------------- #
    # Which pages show (mode-pill, date-nav)
    _NAV_VIS = {
        "overview":      (True,  True),
        "analytics":     (False, True),
        "subscriptions": (False, True),
        "goals":         (False, True),
        "history":       (False, False),
        "settings":      (False, False),
    }

    def go(self, key):
        self.topbar.reset_edit()          # leave edit mode on page change
        self._set_edit_mode(False)
        page = self.pages[key]
        if hasattr(page, "set_context"):
            # non-overview pages are month-based; always hand them a month doc
            md = self.dm.load_month(self.year, self.month)
            if key.startswith("mod:"):            # isolate buggy user modules
                try:
                    page.set_context(md, self.year, self.month)
                except Exception:
                    pass
            else:
                page.set_context(md, self.year, self.month)
        self.stack.setCurrentWidget(page)
        self.sidebar.setActive(key)
        self.topbar.set_title(TITLES[key])
        mv, nv = self._NAV_VIS.get(key, (False, False))
        self.topbar.set_controls_visible(mv, nv)

    def _open_search(self):
        from widgets import SearchDialog
        SearchDialog(self, lambda q: B.search(self.dm, q), self._search_pick).exec()

    def _search_pick(self, result):
        target = result.get("target")
        if not target or target not in self.pages:
            return
        self.go(target)
        if result.get("kind") == "Person" and hasattr(self, "subs"):
            self.subs.tabbar.set_active("People")
            self.subs._switch("People")

    def _apply_sidebar(self):
        """Show/hide sidebar tabs per settings; bounce off a hidden current page."""
        hidden = set(self.dm.settings().get("hidden_tabs", []))
        self.sidebar.apply_hidden(hidden)
        cur_key = next((k for k, p in self.pages.items()
                        if p is self.stack.currentWidget()), None)
        if cur_key in hidden and cur_key not in self.sidebar.ALWAYS:
            self.go("overview")

    # -- time navigation (lens-based) ------------------------------------- #
    def set_mode(self, mode):
        """The Month|Week pill picks the lens (Week → the configured week style)."""
        new_lens = "month" if mode == "month" else self._week_style
        if new_lens == self.lens:
            return
        self.lens = new_lens
        self.dm.set_time_lens(new_lens)
        self.topbar.set_mode(mode)
        self._load_anchor()

    def _set_week_style(self, style):
        """Settings changed the week-lens style; apply live if a week lens is active."""
        self._week_style = style
        if self.lens != "month":
            self.lens = style
            self.dm.set_time_lens(style)
            self._load_anchor()

    def shift_period(self, delta):
        self.anchor = B.step_lens(self.lens, self.anchor, delta)
        self._load_anchor()

    def _goto_today(self):
        self.anchor = self.today
        self._load_anchor()

    def _goto_month_overview(self, year: int, month: int):
        self._jump_to_month(year, month)

    def goto_month(self, year, month):
        self._jump_to_month(year, month)

    def _jump_to_month(self, year, month):
        """Month-picker / analytics jump → switch to the month lens on that month."""
        self.lens = "month"
        self.dm.set_time_lens("month")
        self.topbar.set_mode("month")
        self.anchor = date(year, month, 1)
        self._load_anchor()
        self.go("overview")

    def _load_anchor(self):
        rs, re_, lab = B.range_for_lens(self.lens, self.anchor)
        self.year, self.month = self.anchor.year, self.anchor.month
        if self.lens == "month":
            self.doc = self.dm.load_month(self.year, self.month)
            self.overview.set_month(self.doc, self.year, self.month)
        else:
            self.doc = self.dm.load_range(rs, re_, lab)
            self.overview.set_range(self.doc, self.year, self.month)
        self._sync_nav_label()
        cur = self.stack.currentWidget()
        if cur is not self.overview and hasattr(cur, "set_context"):
            try:
                cur.set_context(self.dm.load_month(self.year, self.month),
                                self.year, self.month)
            except Exception:
                pass                              # never let a user module break refresh

    def _sync_nav_label(self):
        rs, re_, lab = B.range_for_lens(self.lens, self.anchor)
        if self.lens == "month":
            self.topbar.set_month(f"{dm.MONTH_NAMES[self.month].upper()} {self.year}")
            self.topbar.nav.lbl.setToolTip("Click to jump to any month")
        else:
            self.topbar.set_month(lab)
            self.topbar.nav.lbl.setToolTip(
                f"{rs.isoformat()} – {re_.isoformat()}  ·  click to jump to a month")
        available = set(self.dm.list_months())
        self.topbar.set_nav_context(available, self.today, self.year, self.month)

    # -- full data reset -------------------------------------------------- #
    def _reset_all_data(self):
        self.dm.reset_all(self.today.year, self.today.month)
        self.anchor = self.today
        self.lens = "month"
        self.dm.set_time_lens("month")
        self.topbar.set_mode("month")
        self._load_anchor()
        self.go("overview")

    # -- cross-month recurring deletion ----------------------------------- #
    def _delete_recurring(self, name: str, kind: str, scope: str):
        """Legacy cross-month deletion. Unused under the flat store (a definition
        spans all months, so the store's delete already removes it everywhere)."""
        self._data_changed()

    # -- persistence ------------------------------------------------------ #
    def _data_changed(self):
        # Edits already persisted to the store; rebuild views from it.
        self._load_anchor()
        month_doc = self.dm.load_month(self.year, self.month)
        self.analytics._ov.set_context(month_doc, self.year, self.month)


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #
def _register_fonts():
    """Ensure UI fonts exist even when the platform font DB starts empty
    (the head-less 'offscreen' renderer)."""
    from PyQt6.QtGui import QFontDatabase
    fdir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    fonts = (
        # Arial Nova (Windows 11) — the configured family, plus light/regular weights
        "arialnova.ttf", "arialnovalight.ttf", "arialnova_light.ttf",
        "ARIALNOVALT.TTF", "ARIALNOVA.TTF",
        # fallbacks so the UI still renders if Arial Nova isn't installed
        "segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "seguisym.ttf",
    )
    for fname in fonts:
        path = os.path.join(fdir, fname)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
    # graceful fallback for QFont(...) constructions when Arial Nova isn't installed
    QFont.insertSubstitutions(T.FONT_FAMILY, ["Arial", "Segoe UI"])
    QFont.insertSubstitutions(T.FONT_FAMILY_LIGHT, [T.FONT_FAMILY, "Arial", "Segoe UI"])


def main():
    args = sys.argv[1:]
    app = QApplication(sys.argv)
    _register_fonts()
    app.setStyleSheet(T.global_qss())
    app.setFont(QFont(T.FONT_FAMILY, 10))

    if "--shot" in args:
        import widgets
        widgets.ANIMATE = False       # deterministic, fully-revealed charts for capture

    win = MainWindow()

    if "--shot" in args:
        path = args[args.index("--shot") + 1]
        win.resize(T.WIN_W, T.WIN_H)
        win.show()
        if "--page" in args:
            win.go(args[args.index("--page") + 1])
        app.processEvents(); app.processEvents()
        win.grab().save(path)
        print(f"saved {path}")
        return 0

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

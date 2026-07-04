"""CSV export helpers.

Two flavours are offered from the UI:
* a detailed dump of a single month's categories, and
* a one-row-per-month summary across all stored months.
"""

from __future__ import annotations

import csv

import backend as B
import datamanagement as dm


def _rows_for(nodes, section, parent_name=""):
    """Flatten a category tree into export rows, recursing to any depth."""
    for n in nodes:
        amt = B.node_amount(n)
        signed = amt if section == "Income" else -amt
        yield {
            "Section": section,
            "Category": n["name"],
            "Parent": parent_name,
            "Amount": signed,
            "Recurring": "yes" if n.get("recurring") else "",
            "Due": n.get("due") or "",
            "Added": n.get("added") or "",
            "Paid": "yes" if n.get("paid") else "",
        }
        yield from _rows_for(n.get("children", []), section, n["name"])


def export_month_csv(doc: dict, path: str) -> None:
    fields = ["Section", "Category", "Parent", "Amount",
              "Recurring", "Due", "Added", "Paid"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in _rows_for(doc.get("income", []), "Income"):
            w.writerow(r)
        for r in _rows_for(doc.get("expenses", []), "Expense"):
            w.writerow(r)


def export_history_csv(manager: "dm.DataManager", path: str) -> None:
    fields = ["Month", "Income", "Expenses", "P&L", "Savings Rate", "Target P&L"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for y, m in manager.list_months():
            d = manager.load_month(y, m)
            w.writerow({
                "Month": f"{y}-{m:02d}",
                "Income": B.income_total(d),
                "Expenses": B.expense_total(d),
                "P&L": B.pnl(d),
                "Savings Rate": f"{B.savings_rate(d) * 100:.1f}%",
                "Target P&L": d.get("target_pnl", 0),
            })

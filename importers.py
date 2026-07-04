"""Bank statement importers — parse exported transaction files into a plain list
of transaction dicts.  No network, no credentials: the user exports a CSV/OFX
from ANZ / ANZ Plus internet banking and we read the file.

A transaction is::

    {"date": "YYYY-MM-DD", "amount": float, "description": str}

``amount`` keeps the bank's sign convention: **negative = money out (spend)**,
positive = money in.  Account / category / tags are attached later by the store.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime


# --------------------------------------------------------------------------- #
#  Date / amount parsing helpers
# --------------------------------------------------------------------------- #
_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y",
                 "%d %b %Y", "%d %B %Y", "%m/%d/%Y")


def _parse_date(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")        # (12.34) → -12.34
    s = s.strip("()")
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    if s in ("", "-", "+"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


# --------------------------------------------------------------------------- #
#  CSV — flexible column detection (handles ANZ classic + ANZ Plus exports)
# --------------------------------------------------------------------------- #
def parse_csv(text: str) -> list[dict]:
    """Parse CSV text. Detects which columns are date / amount / description,
    with or without a header row, and supports separate debit/credit columns."""
    text = text.lstrip("﻿")                       # strip BOM
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return []

    header = rows[0]
    has_header = not _looks_like_data(header)
    body = rows[1:] if has_header else rows
    cols = _column_map(header, body, has_header)
    out: list[dict] = []
    for r in body:
        txn = _row_to_txn(r, cols)
        if txn:
            out.append(txn)
    return out


def _looks_like_data(row: list[str]) -> bool:
    """A row is data (not a header) if it already contains a parseable date."""
    return any(_parse_date(c) for c in row)


def _column_map(header: list[str], body: list[list[str]], has_header: bool) -> dict:
    """Return {date, amount, debit, credit, desc} → column indices."""
    n = max((len(r) for r in body), default=len(header))
    cols = {"date": None, "amount": None, "debit": None,
            "credit": None, "desc": None}

    if has_header:
        for i, name in enumerate(header):
            key = name.strip().lower()
            if cols["date"] is None and "date" in key:
                cols["date"] = i
            elif "debit" in key:
                cols["debit"] = i
            elif "credit" in key:
                cols["credit"] = i
            elif cols["amount"] is None and ("amount" in key or "value" in key):
                cols["amount"] = i
            elif cols["desc"] is None and any(k in key for k in
                    ("desc", "narrative", "detail", "transaction", "payee", "merchant")):
                cols["desc"] = i

    # Fall back to content sniffing for anything still unknown.
    sample = body[:25]
    if cols["date"] is None:
        cols["date"] = _best_col(sample, n, lambda v: _parse_date(v) is not None)
    if cols["amount"] is None and cols["debit"] is None:
        cols["amount"] = _best_col(sample, n, lambda v: _parse_amount(v) is not None,
                                   exclude={cols["date"]})
    if cols["desc"] is None:
        cols["desc"] = _best_col(sample, n, _is_texty,
                                 exclude={cols["date"], cols["amount"],
                                          cols["debit"], cols["credit"]})
    return cols


def _best_col(sample, n, pred, exclude=frozenset()):
    """Index of the column where ``pred`` holds for the most rows."""
    best, best_score = None, 0
    for i in range(n):
        if i in exclude or i is None:
            continue
        score = sum(1 for r in sample if i < len(r) and pred(r[i]))
        if score > best_score:
            best, best_score = i, score
    return best


def _is_texty(v: str) -> bool:
    v = (v or "").strip()
    return len(v) >= 3 and any(c.isalpha() for c in v) and _parse_amount(v) is None


def _cell(r, i):
    return r[i] if (i is not None and i < len(r)) else ""


def _row_to_txn(r: list[str], cols: dict) -> dict | None:
    date = _parse_date(_cell(r, cols["date"]))
    if not date:
        return None
    if cols["amount"] is not None:
        amount = _parse_amount(_cell(r, cols["amount"]))
    else:                                              # separate debit / credit cols
        deb = _parse_amount(_cell(r, cols["debit"])) or 0.0
        cre = _parse_amount(_cell(r, cols["credit"])) or 0.0
        amount = cre - abs(deb)
    if amount is None:
        return None
    desc = _cell(r, cols["desc"]).strip() or "(no description)"
    return {"date": date, "amount": float(amount), "description": desc}


# --------------------------------------------------------------------------- #
#  OFX / QFX — regex the STMTTRN blocks (works for SGML and XML variants)
# --------------------------------------------------------------------------- #
def parse_ofx(text: str) -> list[dict]:
    out: list[dict] = []
    for block in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text,
                            re.IGNORECASE | re.DOTALL):
        dt  = _tag(block, "DTPOSTED")
        amt = _parse_amount(_tag(block, "TRNAMT") or "")
        if not dt or amt is None:
            continue
        date = _parse_date(dt[:8]) or _parse_date(dt) \
            or (f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}" if len(dt) >= 8 else None)
        if not date:
            continue
        desc = (_tag(block, "NAME") or _tag(block, "MEMO") or "(no description)").strip()
        out.append({"date": date, "amount": float(amt), "description": desc})
    return out


def _tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>([^<\r\n]*)", block, re.IGNORECASE)
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------- #
#  Dispatch
# --------------------------------------------------------------------------- #
def parse_file(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    low = path.lower()
    if low.endswith((".ofx", ".qfx")) or "<OFX>" in text.upper():
        return parse_ofx(text)
    return parse_csv(text)

"""Vector icons drawn with QPainter.

Keeping icons as code (rather than bundled SVG/PNG assets) makes the app a
single self-contained folder and lets every glyph be recoloured on the fly for
hover / active states.  All shapes are authored in a centred unit circle of
radius ``R`` and mapped into the requested rectangle.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _pen(color: str, w: float) -> QPen:
    pen = QPen(QColor(color), w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def draw(p: QPainter, name: str, rect: QRectF, color: str, w: float = 1.6) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = min(rect.width(), rect.height())
    R = s / 2.0
    cx = rect.x() + rect.width() / 2.0
    cy = rect.y() + rect.height() / 2.0

    def pt(nx: float, ny: float) -> QPointF:
        return QPointF(cx + nx * R, cy + ny * R)

    p.setPen(_pen(color, w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    col = QColor(color)

    if name == "overview":
        cell, gap = R * 0.62, R * 0.20
        rad = cell * 0.30
        xs = (cx - cell - gap / 2, cx + gap / 2)
        ys = (cy - cell - gap / 2, cy + gap / 2)
        for x in xs:
            for y in ys:
                p.drawRoundedRect(QRectF(x, y, cell, cell), rad, rad)

    elif name == "income":            # solid up-triangle
        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([pt(0, -0.60), pt(-0.60, 0.52), pt(0.60, 0.52)]))

    elif name == "expenses":          # solid down-triangle
        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([pt(0, 0.60), pt(-0.60, -0.52), pt(0.60, -0.52)]))

    elif name == "analytics":         # up-trend line + arrowhead
        path = QPainterPath(pt(-0.72, 0.46))
        for nx, ny in [(-0.22, -0.04), (0.16, 0.22), (0.68, -0.56)]:
            path.lineTo(pt(nx, ny))
        p.drawPath(path)
        p.drawLine(pt(0.68, -0.56), pt(0.36, -0.52))
        p.drawLine(pt(0.68, -0.56), pt(0.62, -0.22))

    elif name == "goals":             # concentric target
        p.drawEllipse(QPointF(cx, cy), R * 0.80, R * 0.80)
        p.drawEllipse(QPointF(cx, cy), R * 0.46, R * 0.46)
        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), R * 0.15, R * 0.15)

    elif name == "history":           # clock
        p.drawEllipse(QPointF(cx, cy), R * 0.78, R * 0.78)
        p.drawLine(QPointF(cx, cy), pt(0, -0.44))
        p.drawLine(QPointF(cx, cy), pt(0.34, 0.10))

    elif name == "settings":          # gear: ring + teeth
        for i in range(8):
            a = math.pi * i / 4.0
            p.drawLine(pt(0.50 * math.cos(a), 0.50 * math.sin(a)),
                       pt(0.82 * math.cos(a), 0.82 * math.sin(a)))
        p.drawEllipse(QPointF(cx, cy), R * 0.50, R * 0.50)
        p.drawEllipse(QPointF(cx, cy), R * 0.20, R * 0.20)

    elif name == "today":   # calendar page: rect + tabs + header line + date dot
        pad = R * 0.18
        bx, by = cx - R + pad, cy - R * 0.54
        bw, bh = 2 * (R - pad), R * 1.48
        p.drawRect(QRectF(bx, by, bw, bh))
        for dx in (-R * 0.30, R * 0.30):          # binding tabs
            p.drawLine(QPointF(cx + dx, by), QPointF(cx + dx, by - R * 0.34))
        p.drawLine(QPointF(bx, by + bh * 0.34),   # header separator
                   QPointF(bx + bw, by + bh * 0.34))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(cx, by + bh * 0.70), R * 0.20, R * 0.20)  # today dot

    elif name == "chevron_left":
        path = QPainterPath(pt(0.22, -0.46)); path.lineTo(pt(-0.24, 0)); path.lineTo(pt(0.22, 0.46))
        p.drawPath(path)
    elif name == "chevron_right":
        path = QPainterPath(pt(-0.22, -0.46)); path.lineTo(pt(0.24, 0)); path.lineTo(pt(-0.22, 0.46))
        p.drawPath(path)

    elif name == "plus":
        p.drawLine(pt(-0.5, 0), pt(0.5, 0))
        p.drawLine(pt(0, -0.5), pt(0, 0.5))

    elif name == "budget":            # balance scale (ideal vs actual)
        p.drawLine(pt(0, -0.70), pt(0, 0.55))            # central post
        p.drawLine(pt(-0.62, -0.40), pt(0.62, -0.40))    # beam
        for sx in (-0.62, 0.62):                          # hangers + pans
            p.drawLine(pt(sx, -0.40), pt(sx, -0.10))
            path = QPainterPath(pt(sx - 0.26, -0.10))
            path.quadTo(pt(sx, 0.18), pt(sx + 0.26, -0.10))
            p.drawPath(path)
        p.drawLine(pt(-0.34, 0.55), pt(0.34, 0.55))      # base

    elif name == "subs":              # subscriptions: recurring-cycle ring + arrow
        rr = R * 0.62
        p.drawArc(QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr), 40 * 16, 280 * 16)
        ah = pt(0.46, -0.42)
        p.drawLine(ah, pt(0.16, -0.36))
        p.drawLine(ah, pt(0.50, -0.10))
        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), R * 0.13, R * 0.13)

    elif name == "recurring":         # repeat: two arc arrows (refresh cycle)
        rr = R * 0.60
        rect2 = QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr)
        p.drawArc(rect2, 60 * 16, 150 * 16)              # top arc
        p.drawArc(rect2, 240 * 16, 150 * 16)             # bottom arc
        a1 = pt(0.52, 0.10); p.drawLine(a1, pt(0.30, 0.04)); p.drawLine(a1, pt(0.40, 0.34))
        a2 = pt(-0.52, -0.10); p.drawLine(a2, pt(-0.30, -0.04)); p.drawLine(a2, pt(-0.40, -0.34))

    elif name == "search":            # magnifier
        p.drawEllipse(QPointF(cx - R * 0.16, cy - R * 0.16), R * 0.5, R * 0.5)
        p.drawLine(pt(0.30, 0.30), pt(0.66, 0.66))

    # ---- ledger-row action glyphs (their own column, hover-revealed) -------- #
    # Authored to sit together as a set: same line weight, same optical size, so
    # the actions column reads as one control group rather than four borrowed
    # Unicode characters at four different metrics.
    elif name == "tag":               # luggage/price tag + eyelet
        path = QPainterPath(pt(-0.62, 0.0))          # pointed left tip
        path.lineTo(pt(-0.16, -0.52))
        path.lineTo(pt(0.60, -0.52))
        path.lineTo(pt(0.60, 0.52))
        path.lineTo(pt(-0.16, 0.52))
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QPointF(cx - R * 0.24, cy), R * 0.10, R * 0.10)   # eyelet

    elif name == "note":              # pencil: shaft + sharpened nib + ferrule
        p.drawLine(pt(0.40, -0.40), pt(-0.34, 0.34))          # shaft
        p.drawLine(pt(-0.34, 0.34), pt(-0.54, 0.54))          # nib to point
        p.drawLine(pt(-0.50, 0.30), pt(-0.54, 0.54))          # nib edge
        p.drawLine(pt(0.18, -0.34), pt(0.34, -0.18))          # metal ferrule band

    elif name == "trash":             # waste bin: lid + handle + tapered body + ribs
        p.drawLine(pt(-0.54, -0.30), pt(0.54, -0.30))         # lid line
        hp = QPainterPath(pt(-0.20, -0.30))                   # handle
        hp.lineTo(pt(-0.20, -0.50)); hp.lineTo(pt(0.20, -0.50)); hp.lineTo(pt(0.20, -0.30))
        p.drawPath(hp)
        bp = QPainterPath(pt(-0.42, -0.30))                   # tapered body
        bp.lineTo(pt(-0.32, 0.52)); bp.lineTo(pt(0.32, 0.52)); bp.lineTo(pt(0.42, -0.30))
        p.drawPath(bp)
        p.drawLine(pt(-0.12, -0.08), pt(-0.10, 0.34))         # ribs
        p.drawLine(pt(0.12, -0.08), pt(0.10, 0.34))

    elif name == "cross":             # clean delete/close X (vector, not the "✕" glyph)
        p.drawLine(pt(-0.42, -0.42), pt(0.42, 0.42))
        p.drawLine(pt(0.42, -0.42), pt(-0.42, 0.42))

    elif name == "plus_sub":          # add sub-item: small corner elbow + bold plus
        p.drawLine(pt(-0.62, -0.55), pt(-0.62, -0.15))        # short elbow down…
        p.drawLine(pt(-0.62, -0.15), pt(-0.30, -0.15))        # …then right
        p.drawLine(pt(0.14, -0.34), pt(0.14, 0.42))          # bold plus (dominant)
        p.drawLine(pt(-0.24, 0.04), pt(0.52, 0.04))

    elif name == "module":            # plugin: 2×2 blocks
        s2 = R * 0.42; gap = R * 0.16; rad = s2 * 0.25
        for ox in (-s2 - gap / 2, gap / 2):
            for oy in (-s2 - gap / 2, gap / 2):
                p.drawRoundedRect(QRectF(cx + ox, cy + oy, s2, s2), rad, rad)

    elif name == "networth":          # stacked coins (assets)
        for i, yy in enumerate((0.46, 0.06, -0.34)):
            p.drawEllipse(QRectF(cx - R * 0.62, cy + yy * R - R * 0.13,
                                 R * 1.24, R * 0.26))

    elif name == "dollar":            # logo glyph
        f = p.font(); f.setPointSizeF(R * 1.05); f.setBold(True); p.setFont(f)
        p.setPen(_pen(color, w))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "$")

    p.restore()


def pixmap(name: str, color: str, size: int, w: float = 1.6) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    draw(p, name, QRectF(0, 0, size, size), color, w)
    p.end()
    return pm

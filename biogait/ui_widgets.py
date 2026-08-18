"""Reusable UI widgets for the BioGait desktop app."""
from __future__ import annotations

from collections import deque
from typing import Any, Optional

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy,
    QVBoxLayout, QWidget
)

# ── Design tokens ─────────────────────────────────────────────────────────────
BG_DARK  = "#0d1117"
BG_CARD  = "#161b22"
BG_PANEL = "#13181f"
ACCENT   = "#1f6feb"
TEXT_PRI = "#e6edf3"
TEXT_SEC = "#8b949e"
BORDER   = "#30363d"

RISK_COLORS = {
    "LOW":      "#2ea043",
    "MODERATE": "#d29922",
    "HIGH":     "#f85149",
}

STATUS_COLORS = {
    "TRACKING":    "#2ea043",
    "NO_POSE":     "#d29922",
    "CONNECTING":  "#8b949e",
    "NO_SIGNAL":   "#f85149",
    "RECONNECTING": "#d29922",
    "ERROR":       "#f85149",
    "STOPPED":     "#8b949e",
}


# ── MetricCard ────────────────────────────────────────────────────────────────
class MetricCard(QFrame):
    def __init__(self, label: str, unit: str = "") -> None:
        super().__init__()
        self._unit = unit
        self.setFixedHeight(106)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:10px; font-weight:700; letter-spacing:1.5px;"
        )
        self._val = QLabel("--")
        self._val.setStyleSheet(f"color:{TEXT_PRI}; font-size:30px; font-weight:700;")
        lay.addWidget(self._lbl)
        lay.addWidget(self._val)
        lay.addStretch()

    def set_value(self, value: Any, color: str = TEXT_PRI) -> None:
        txt = "--" if value is None else f"{value}{self._unit}"
        self._val.setText(txt)
        self._val.setStyleSheet(f"color:{color}; font-size:30px; font-weight:700;")


# ── RiskGauge ─────────────────────────────────────────────────────────────────
class RiskGauge(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(96)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        row = QHBoxLayout()
        self._level = QLabel("LOW RISK")
        self._level.setStyleSheet(
            f"color:{RISK_COLORS['LOW']}; font-size:10px; font-weight:700; letter-spacing:1.5px;"
        )
        self._score = QLabel("0 / 100")
        self._score.setStyleSheet(f"color:{TEXT_PRI}; font-size:22px; font-weight:700;")
        row.addWidget(self._level)
        row.addStretch()
        row.addWidget(self._score)
        lay.addLayout(row)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(14)
        self._apply_bar_style(RISK_COLORS["LOW"])
        lay.addWidget(self._bar)

    def _apply_bar_style(self, color: str) -> None:
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: #21262d;
                border-radius: 7px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 7px;
            }}
        """)

    def set_risk(self, score: int, level: str) -> None:
        color = RISK_COLORS.get(level, RISK_COLORS["LOW"])
        self._bar.setValue(max(0, min(100, score)))
        self._level.setText(f"{level} RISK")
        self._level.setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:700; letter-spacing:1.5px;"
        )
        self._score.setText(f"{score} / 100")
        self._apply_bar_style(color)


# ── SparklineChart ────────────────────────────────────────────────────────────
class SparklineChart(QWidget):
    def __init__(self, label: str, color: str = "#388bfd", maxpts: int = 60) -> None:
        super().__init__()
        self._label = label
        self._color = color
        self._data: deque[float] = deque(maxlen=maxpts)
        self.setFixedHeight(72)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def add(self, value: Optional[float]) -> None:
        if value is not None:
            self._data.append(float(value))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if len(self._data) < 2:
            return
        p  = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top  = 16   # space for label
        bot  = 4

        # label
        f = QFont(); f.setPixelSize(10); f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT_SEC))
        p.drawText(0, 12, self._label)

        data = list(self._data)
        mn, mx = min(data), max(data)
        rng = (mx - mn) or 1.0
        pts = [
            QPointF(
                i / (len(data) - 1) * (w - 2) + 1,
                top + (1 - (v - mn) / rng) * (h - top - bot)
            )
            for i, v in enumerate(data)
        ]

        # fill gradient
        g = QLinearGradient(0, top, 0, h)
        c = QColor(self._color); c.setAlpha(70)
        g.setColorAt(0, c); c.setAlpha(0); g.setColorAt(1, c)
        fp = QPainterPath()
        fp.moveTo(pts[0].x(), h)
        for pt in pts: fp.lineTo(pt)
        fp.lineTo(pts[-1].x(), h)
        fp.closeSubpath()
        p.fillPath(fp, QBrush(g))

        # line
        lp = QPainterPath()
        lp.moveTo(pts[0])
        for pt in pts[1:]: lp.lineTo(pt)
        p.setPen(QPen(QColor(self._color), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(lp)

        # dot at latest point
        p.setBrush(QBrush(QColor(self._color))); p.setPen(Qt.NoPen)
        p.drawEllipse(pts[-1], 4, 4)
        p.end()


# ── ReasonsBox ────────────────────────────────────────────────────────────────
class ReasonsBox(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        hdr = QLabel("ASSESSMENT")
        hdr.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:10px; font-weight:700; letter-spacing:1.5px;"
        )
        self._body = QLabel("Waiting for pose data...")
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color:{TEXT_PRI}; font-size:12px; line-height:1.6;")
        self._body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lay.addWidget(hdr)
        lay.addWidget(self._body)
        lay.addStretch()

    def set_reasons(self, reasons: list[str]) -> None:
        self._body.setText("\n".join(f"• {r}" for r in reasons) if reasons else "No issues detected.")

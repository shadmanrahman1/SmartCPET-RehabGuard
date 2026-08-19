"""Reusable UI widgets for the BioGait desktop app."""
from __future__ import annotations

from collections import deque
from typing import Any, Optional

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy,
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


# ── ResearchEvidencePanel ─────────────────────────────────────────────────────
class ResearchEvidencePanel(QFrame):
    """Small research-only display for KIMORE-informed evidence (Sprint A).

    Shows descriptive kinematics only. It deliberately shows NO correct/
    incorrect, no clinical score, no pass/fail, and no clinical colour
    semantics. Keep this panel information-neutral.
    """

    # Emitted when the user presses "Generate Evidence Summary". A bounded
    # explainer is run asynchronously OFF the capture thread.
    generate_summary_requested = pyqtSignal()
    # Emitted when the user presses "Export Research Session".
    export_session_requested = pyqtSignal()

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

        hdr = QLabel("RESEARCH EVIDENCE — KIMORE-INFORMED")
        hdr.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:10px; font-weight:700; letter-spacing:1px;"
        )
        lay.addWidget(hdr)

        sub = QLabel("Descriptive kinematics only — not a clinical score")
        sub.setStyleSheet(f"color:{TEXT_SEC}; font-size:9px;")
        lay.addWidget(sub)

        self._rows: dict[str, QLabel] = {}
        self._units: dict[str, str] = {}
        row_specs = [
            ("L sagittal knee", "°"),
            ("R sagittal knee", "°"),
            ("Current PO evidence", ""),
            ("Rolling PO availability", ""),
            ("Rolling L ROM", "°"),
            ("Rolling R ROM", "°"),
            ("Session state", ""),
            ("Processed frames", ""),
            ("Research elapsed", "s"),
        ]
        for label, unit in row_specs:
            self._units[label] = unit
            grid = QHBoxLayout(); grid.setSpacing(8)
            name = QLabel(label)
            name.setStyleSheet(
                f"color:{TEXT_SEC}; font-size:10px; font-weight:600;"
            )
            val = QLabel("--")
            val.setStyleSheet(f"color:{TEXT_PRI}; font-size:12px; font-weight:600;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(name)
            grid.addStretch()
            grid.addWidget(val)
            self._rows[label] = val
            lay.addLayout(grid)

        # Causal-filter observability status (default disabled).
        self._causal_status_label = QLabel("Causal filter: disabled")
        self._causal_status_label.setStyleSheet(f"color:{TEXT_SEC}; font-size:9px;")
        lay.addWidget(self._causal_status_label)

        # ── Evidence Summary (bounded explanation) ─────────────────────────
        lay.addSpacing(4)
        sum_hdr = QLabel("Evidence Summary")
        sum_hdr.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:10px; font-weight:700; letter-spacing:1px;"
        )
        lay.addWidget(sum_hdr)
        self._summary_label = QLabel(
            "No summary yet. Press 'Generate Evidence Summary'."
        )
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(f"color:{TEXT_PRI}; font-size:9px;")
        lay.addWidget(self._summary_label)
        gen_btn = QPushButton("Generate Evidence Summary")
        gen_btn.setStyleSheet(
            f"QPushButton {{ background:{TEXT_SEC}; color:{BG_CARD}; "
            f"border:none; padding:6px 10px; border-radius:6px; }}"
        )
        gen_btn.clicked.connect(self.generate_summary_requested.emit)
        gen_btn.setEnabled(False)  # disabled until the first research evidence
        self._gen_button = gen_btn
        lay.addWidget(gen_btn)

        # Export Research Session (explicit user action).
        export_btn = QPushButton("Export Research Session")
        export_btn.setStyleSheet(
            f"QPushButton {{ background:{TEXT_SEC}; color:{BG_CARD}; "
            f"border:none; padding:6px 10px; border-radius:6px; }}"
        )
        export_btn.clicked.connect(self.export_session_requested.emit)
        lay.addWidget(export_btn)
        self._export_message = QLabel("")
        self._export_message.setWordWrap(True)
        self._export_message.setStyleSheet(f"color:{TEXT_SEC}; font-size:9px;")
        lay.addWidget(self._export_message)

    def set_evidence_summary(self, text: str) -> None:
        self._summary_label.setText(text or "No summary available.")

    def set_generate_enabled(self, enabled: bool) -> None:
        self._gen_button.setEnabled(enabled)

    def set_export_message(self, text: str) -> None:
        self._export_message.setText(text)

    def update_research_evidence(self, payload: dict) -> None:
        def _fmt(name: str, value, digits: int = 1) -> str:
            if value is None:
                return "--"
            unit = self._units.get(name, "")
            if isinstance(value, float):
                return f"{value:.{digits}f}{unit}"
            return f"{value}{unit}"

        # Enable the evidence-summary action only once real research evidence
        # exists (never before the first processed frame).
        if (payload.get("quality") or payload.get("primary_outcomes")):
            self._gen_button.setEnabled(True)

        self._rows["L sagittal knee"].setText(
            _fmt("L sagittal knee", payload.get("left_knee_sagittal_deg"))
        )
        self._rows["R sagittal knee"].setText(
            _fmt("R sagittal knee", payload.get("right_knee_sagittal_deg"))
        )

        quality = payload.get("quality") or {}
        state = payload.get("current_po_state")
        if not state:
            left_ok = quality.get("left_po_available", False)
            right_ok = quality.get("right_po_available", False)
            state = "complete" if (left_ok and right_ok) else (
                "partial" if (left_ok or right_ok) else "unavailable"
            )
        self._rows["Current PO evidence"].setText(state)

        rate = payload.get("rolling_po_availability_rate")
        self._rows["Rolling PO availability"].setText(
            f"{rate * 100:.1f}%" if isinstance(rate, (int, float)) else "--"
        )

        # Rolling window ROM (last-300-processed-frame window), never billed
        # as whole-session ROM.
        self._rows["Rolling L ROM"].setText(
            _fmt("Rolling L ROM", payload.get("rolling_left_knee_rom_deg"))
        )
        self._rows["Rolling R ROM"].setText(
            _fmt("Rolling R ROM", payload.get("rolling_right_knee_rom_deg"))
        )

        # Information-neutral session state / progress.
        self._rows["Session state"].setText(
            str(payload.get("session_state") or "IDLE")
        )
        frames = payload.get("processed_frames")
        self._rows["Processed frames"].setText(str(frames) if frames is not None else "--")
        self._rows["Research elapsed"].setText(
            _fmt("Research elapsed", payload.get("research_elapsed_seconds"))
        )

        # Optional causal-filter observability (raw values are never replaced).
        if "causal_filter_status" in payload:
            causal_status = payload.get("causal_filter_status")
            if self._causal_status_label is not None:
                self._causal_status_label.setText(
                    f"Causal filter: {causal_status}" if causal_status else "Causal filter: disabled"
                )

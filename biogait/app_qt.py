"""
SmartCPET-RehabGuard BioGait — Desktop App
==========================================
Split-panel window: live MediaPipe video (left) + metrics dashboard (right).
Run:  python app_qt.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)


def _atomic_write_json(path: Path, obj) -> None:
    """Write JSON atomically with allow_nan=False (no identity/path leaks)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

import config
from ui_widgets import (
    BG_CARD, BG_DARK, BG_PANEL, BORDER, RISK_COLORS,
    STATUS_COLORS, TEXT_PRI, TEXT_SEC,
    MetricCard, ReasonsBox, ResearchEvidencePanel, RiskGauge, SparklineChart,
)
from ui_worker import CameraWorker, ExplanationWorker
from explanation_ui import evidence_from_payload


# ── Video Panel ───────────────────────────────────────────────────────────────
class VideoPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(f"background:{BG_DARK};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 8, 16)
        lay.setSpacing(10)

        # title
        t = QLabel("📷  LIVE FEED")
        t.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:11px; font-weight:700; letter-spacing:2px;"
        )
        lay.addWidget(t)

        # video display
        self._img = QLabel("Connecting to camera…")
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._img.setStyleSheet(
            f"background:#000; color:{TEXT_SEC}; font-size:14px;"
            f" border:1px solid {BORDER}; border-radius:10px;"
        )
        lay.addWidget(self._img, 1)

        # status pill
        self._status = QLabel("● CONNECTING")
        self._status.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:12px; font-weight:700;"
        )
        lay.addWidget(self._status)

    def update_frame(self, qt_image) -> None:
        px = QPixmap.fromImage(qt_image)
        self._img.setPixmap(
            px.scaled(self._img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def update_status(self, status: str) -> None:
        color = STATUS_COLORS.get(status, TEXT_SEC)
        self._status.setText(f"● {status}")
        self._status.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:700;"
        )


# ── Dashboard Panel ───────────────────────────────────────────────────────────
class DashboardPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._t0 = time.time()
        self.setStyleSheet(f"background:{BG_PANEL};")
        self.setFixedWidth(460)

        # scroll wrapper so nothing clips on small screens
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")

        inner = QWidget()
        inner.setStyleSheet(f"background:{BG_PANEL};")
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 16, 16, 16)
        lay.setSpacing(10)

        # ── header ──────────────────────────────────────────────────────────
        hrow = QHBoxLayout()
        title = QLabel("SmartCPET BioGait")
        title.setStyleSheet(
            f"color:{TEXT_PRI}; font-size:20px; font-weight:800;"
        )
        self._timer_lbl = QLabel("00:00")
        self._timer_lbl.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:14px; font-weight:600;"
        )
        hrow.addWidget(title); hrow.addStretch(); hrow.addWidget(self._timer_lbl)
        lay.addLayout(hrow)

        sub = QLabel("Real-time pose analysis  ·  Screening only — not clinical")
        sub.setStyleSheet(f"color:{TEXT_SEC}; font-size:10px;")
        lay.addWidget(sub)

        # separator
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{BORDER}; max-height:1px; margin:4px 0;")
        lay.addWidget(sep)

        # ── risk gauge ───────────────────────────────────────────────────────
        self._gauge = RiskGauge()
        lay.addWidget(self._gauge)

        gauge_cap = QLabel("Legacy experimental baseline — not clinically validated")
        gauge_cap.setStyleSheet(f"color:{TEXT_SEC}; font-size:9px;")
        lay.addWidget(gauge_cap)

        # ── research evidence (KIMORE-informed, descriptive only) ────────────
        self._research = ResearchEvidencePanel()
        lay.addWidget(self._research)

        # ── metric cards (2 × 2) ─────────────────────────────────────────────
        self._lk    = MetricCard("Left Knee",  " °")
        self._rk    = MetricCard("Right Knee", " °")
        self._trunk = MetricCard("Trunk Lean", " °")
        self._asym  = MetricCard("Asymmetry",  " °")
        for row_cards in ((self._lk, self._rk), (self._trunk, self._asym)):
            row = QHBoxLayout(); row.setSpacing(10)
            for c in row_cards: row.addWidget(c)
            lay.addLayout(row)

        # ── sparklines ───────────────────────────────────────────────────────
        slbl = QLabel("TREND — LAST 60 FRAMES")
        slbl.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:10px; font-weight:700; letter-spacing:1px;"
        )
        lay.addWidget(slbl)

        srow = QHBoxLayout(); srow.setSpacing(10)
        self._sk_lk    = SparklineChart("L-Knee",  "#388bfd")
        self._sk_rk    = SparklineChart("R-Knee",  "#3fb950")
        self._sk_trunk = SparklineChart("Trunk",   "#d29922")
        for s in (self._sk_lk, self._sk_rk, self._sk_trunk):
            srow.addWidget(s)
        lay.addLayout(srow)

        # ── assessment / reasons ─────────────────────────────────────────────
        self._reasons = ReasonsBox()
        lay.addWidget(self._reasons)
        lay.addStretch()

        # session timer
        self._tick = QTimer()
        self._tick.timeout.connect(self._update_timer)
        self._tick.start(1000)

    def _update_timer(self) -> None:
        e = int(time.time() - self._t0)
        m, s = divmod(e, 60)
        self._timer_lbl.setText(f"{m:02d}:{s:02d}")

    def update_metrics(self, m: dict) -> None:
        lk    = m.get("left_knee_angle")
        rk    = m.get("right_knee_angle")
        trunk = m.get("trunk_lean")
        asym  = m.get("knee_asymmetry")
        score = int(m.get("risk_score", 0))
        level = m.get("risk_level", "LOW")

        def _asym_color(v):
            if v is None:  return TEXT_SEC
            if v > 20:     return RISK_COLORS["HIGH"]
            if v > 12:     return RISK_COLORS["MODERATE"]
            return TEXT_PRI

        self._lk.set_value(lk)
        self._rk.set_value(rk)
        self._trunk.set_value(trunk)
        self._asym.set_value(asym, _asym_color(asym))
        self._gauge.set_risk(score, level)
        self._reasons.set_reasons(m.get("reasons", []))
        self._sk_lk.add(lk)
        self._sk_rk.add(rk)
        self._sk_trunk.add(trunk)

    def update_research_evidence(self, payload: dict) -> None:
        self._research.update_research_evidence(payload)


# ── Main Window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SmartCPET-RehabGuard  |  BioGait Live")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(f"background:{BG_DARK};")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._video     = VideoPanel()
        self._dashboard = DashboardPanel()

        layout.addWidget(self._video,     stretch=1)
        layout.addWidget(self._dashboard, stretch=0)

        # divider line
        self._dashboard.setStyleSheet(
            f"background:{BG_PANEL}; border-left:1px solid {BORDER};"
        )

        # ── worker thread ────────────────────────────────────────────────────
        self._thread = QThread()
        self._worker = CameraWorker(config.get_camera_source())
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.frame_ready.connect(self._video.update_frame)
        self._worker.metrics_ready.connect(self._dashboard.update_metrics)
        self._worker.status_ready.connect(self._video.update_status)
        self._worker.evidence_ready.connect(self._dashboard.update_research_evidence)
        self._dashboard._research.generate_summary_requested.connect(
            self._generate_evidence_summary
        )
        self._dashboard._research.export_session_requested.connect(
            self._export_research_session
        )

        self._thread.start()

    def _evidence_has_content(self) -> bool:
        payload = self._worker.latest_evidence_payload()
        # Require at least one processed evidence frame before offering summaries.
        return bool(payload and payload.get("quality") or payload.get("primary_outcomes"))

    def _generate_evidence_summary(self) -> None:
        """Run a bounded explanation asynchronously OFF the capture thread.

        Uses only structured evidence; never raw frames or identity. Before the
        first processed evidence frame the button is disabled and no request is
        made. The validated summary STRING is shown; an audit dict is never
        routed through the QLabel text slot.
        """
        panel = self._dashboard._research
        if not self._evidence_has_content():
            panel.set_generate_enabled(False)
            panel.set_evidence_summary("NO_EVIDENCE_AVAILABLE")
            return
        evidence = evidence_from_payload(self._worker.latest_evidence_payload())
        panel.set_generate_enabled(False)
        panel.set_evidence_summary("Generating evidence summary...")

        def _on_result(audit: dict) -> None:
            # Extract the validated summary string; never pass a dict to a text
            # label. Biography owns the safety note; we show only the summary.
            output = audit.get("output") or {}
            summary = str(output.get("summary") or "No summary.")
            panel.set_evidence_summary(summary)
            panel.set_generate_enabled(True)
            # Clean up the finished thread.
            if getattr(runner, "finished_ok", None) is not None:
                pass
            runner.deleteLater()

        def _on_finished(ok: bool) -> None:
            panel.set_generate_enabled(True)

        runner = ExplanationWorker(evidence)
        # Track the single active thread for lifecycle cleanup on close.
        self._explanation_thread = runner
        runner.result_ready.connect(_on_result)
        runner.finished_ok.connect(_on_finished)
        runner.request_explanation()

    def _export_research_session(self) -> None:
        """Export the current retained/full research session to a user file."""
        from PyQt5.QtWidgets import QFileDialog

        panel = self._dashboard._research
        try:
            default_name = "biogait_research_session.json"
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Research Session", default_name,
                "BioGait session JSON (*.json)",
            )
            if not path:
                panel.set_export_message("Export cancelled.")
                return
            export = self._worker.export_research_session()
            _atomic_write_json(Path(path), export)
            panel.set_export_message(f"Exported: {Path(path).name}")
        except Exception as exc:  # noqa: BLE001 - show neutral failure text
            panel.set_export_message("Export failed.")

    def closeEvent(self, event) -> None:  # noqa: N802
        # Safely stop the camera thread and any in-flight explanation thread.
        self._worker.stop()
        self._thread.quit()
        self._thread.wait(3000)
        runner = getattr(self, "_explanation_thread", None)
        if runner is not None and runner.isRunning():
            runner.quit()
            runner.wait(2000)
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")

    # dark palette for native widgets (title bar, scrollbars, etc.)
    from PyQt5.QtGui import QPalette
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(13, 17, 23))
    pal.setColor(QPalette.WindowText,      QColor(230, 237, 243))
    pal.setColor(QPalette.Base,            QColor(22, 27, 34))
    pal.setColor(QPalette.AlternateBase,   QColor(13, 17, 23))
    pal.setColor(QPalette.Text,            QColor(230, 237, 243))
    pal.setColor(QPalette.Button,          QColor(22, 27, 34))
    pal.setColor(QPalette.ButtonText,      QColor(230, 237, 243))
    pal.setColor(QPalette.Highlight,       QColor(31, 111, 235))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

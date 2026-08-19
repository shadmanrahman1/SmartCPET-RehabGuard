"""Shared helpers for BioGait evaluation tooling (Sprint B).

Small, deterministic, offline-only utilities used by the experiment modules.
No camera, no dataset download, no clinical claims. All result JSON is written
with ``allow_nan=False`` (invalid numeric values never become NaN/Infinity).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
BIOGAIT_DIR = REPO_ROOT / "biogait"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def opaque_key(*parts: str, length: int = 12) -> str:
    """A neutral, deterministic opaque key from the given parts.

    Parts may include relative path segments; the returned key is a hex digest
    only, so no participant name or local path ever leaks into a result file.
    """
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def atomic_json_write(path: Path, obj: Any) -> None:
    """Write a JSON object atomically (allow_nan=False)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path) -> Any:
    """Load a JSON file (tolerates an absent file by returning None)."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def to_landmarks(joint_role_values: Mapping[str, Mapping[str, Iterable[float]]], index: int) -> dict:
    """Build a single-frame MediaPipe-style landmark dict from joint streams.

    ``joint_role_values`` maps a BioGait landark name
    (e.g. ``left_knee``) to ``{"x": [...], "y": [...], "z": [...]}`` arrays
    indexed by frame. KIMORE-derived coordinates are treated as finite; a
    non-finite value marks that landmark unavailable for that frame.
    """
    out: dict[str, dict[str, float]] = {}
    for name, axes in joint_role_values.items():
        try:
            x = float(axes["x"][index])
            y = float(axes["y"][index])
            z = float(axes["z"][index])
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        if not all(map(_finite, (x, y, z))):
            continue
        out[name] = {"x": x, "y": y, "z": z, "visibility": 1.0}
    return out


def _finite(v: Any) -> bool:
    import math
    return isinstance(v, (int, float)) and math.isfinite(float(v))

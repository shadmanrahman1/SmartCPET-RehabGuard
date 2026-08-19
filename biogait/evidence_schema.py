"""BioGait stable research evidence schema (Sprint C, C1).

Formalizes the canonical versioned BioGait research session/envelope without
duplicating FrameEvidence (per-frame evidence stays in evidence_features.py;
the session envelope adds module/origin/processing-mode and validation).

This schema intentionally carries NO clinical interpretation: no clinical
score, no pass/fail, no diagnosis. ``data_origin`` and ``processing_mode``
describe the input source; ``method_provenance`` describes the method.

Validation helpers reject:
- NaN / Infinity anywhere (allow_nan=False style)
- forbidden identity keys (structural; values are not substring-scanned)
- invalid provenance / data-origin / processing-mode enum values
"""
from __future__ import annotations

import math
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
MODULE = "biogait"
RESEARCH_EXERCISE = "kimore_ex5_squat"

VALID_DATA_ORIGINS = {
    "SYNTHETIC_FIXTURE",
    "REAL_KIMORE_NATIVE_SKELETON",
    "REAL_VIDEO_MEDIAPIPE",
    "UNKNOWN_UNVALIDATED",
}

VALID_PROCESSING_MODES = {
    "live_mediapipe",
    "offline_mediapipe_video",
    "kimore_native_skeleton",
    "synthetic_fixture",
}

VALID_METHOD_PROVENANCE = {
    "REFERENCE_DERIVED",
    "ENGINEERING_ADAPTED",
    "DESCRIPTIVE",
    "EXPERIMENTAL",
}

# Structural forbidden KEYS (recursive). Values are NOT substring-scanned, so
# benign scientific text (e.g. a "landmark name") is never rejected.
FORBIDDEN_IDENTITY_KEYS = {
    "patient",
    "patient_id",
    "patient_name",
    "participant_id",
    "participant_name",
    "subject_name",
    "subject_id",
    "email",
}

# Keys whose VALUES must be drawn from a controlled enum when present.
_ENUM_KEYS = {
    "classification": VALID_METHOD_PROVENANCE,
    "method_provenance": VALID_METHOD_PROVENANCE,
    "data_origin": VALID_DATA_ORIGINS,
    "processing_mode": VALID_PROCESSING_MODES,
}


class SchemaValidationError(ValueError):
    """Raised when an evidence record violates the BioGait research schema."""


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def session_header(
    *,
    data_origin: str,
    processing_mode: str,
    exercise: str = RESEARCH_EXERCISE,
    schema_version: str = SCHEMA_VERSION,
) -> dict:
    """Build the canonical session-header envelope (validated)."""
    return validate_envelope(
        {
            "schema_version": schema_version,
            "module": MODULE,
            "exercise": exercise,
            "data_origin": data_origin,
            "processing_mode": processing_mode,
        }
    )


def validate_envelope(envelope: dict) -> dict:
    """Validate/return a session envelope's enum fields."""
    errors: list[str] = []
    for key, value in envelope.items():
        if key == "classification" or key == "method_provenance":
            if value not in VALID_METHOD_PROVENANCE:
                errors.append(f"invalid method_provenance: {value!r}")
        elif key == "data_origin":
            if value not in VALID_DATA_ORIGINS:
                errors.append(f"invalid data_origin: {value!r}")
        elif key == "processing_mode":
            if value not in VALID_PROCESSING_MODES:
                errors.append(f"invalid processing_mode: {value!r}")
    if errors:
        raise SchemaValidationError("; ".join(errors))
    return dict(envelope)


def validate_evidence_record(obj: Any, path: str = "") -> None:
    """Recursively validate an evidence record.

    Raises ``SchemaValidationError`` on NaN/Infinity, a forbidden identity
    key, or an invalid enum value. ``None`` values (missing evidence) are
    allowed — missing is never fabricated as 0.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_name = str(key)
            if key_name in FORBIDDEN_IDENTITY_KEYS:
                raise SchemaValidationError(
                    f"forbidden identity key {key_name!r} at {path or '<root>'}"
                )
            if key_name in _ENUM_KEYS and value is not None:
                if value not in _ENUM_KEYS[key_name]:
                    raise SchemaValidationError(
                        f"invalid {key_name} value {value!r} at {path or '<root>'}"
                    )
            validate_evidence_record(value, f"{path}.{key_name}" if path else key_name)
    elif isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            validate_evidence_record(item, f"{path}[{index}]")
    elif isinstance(obj, (int, float)):
        if not _finite(obj):
            raise SchemaValidationError(f"non-finite value {obj!r} at {path or '<root>'}")
    # strings / None / bools are structurally allowed


def iter_non_none_numbers(obj: Any) -> Iterable[float]:
    """Yield all finite numeric leaf values (for digests/checks)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from iter_non_none_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from iter_non_none_numbers(item)
    elif isinstance(obj, (int, float)) and obj is not None and not isinstance(obj, bool):
        yield float(obj)

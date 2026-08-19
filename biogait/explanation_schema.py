"""Bounded BioGait explanation input contract (Sprint C, C6).

The explainer (template or remote OpenRouter) receives ONLY a whitelisted
subset of structured evidence. It NEVER receives:

- raw video, video frames, or a camera stream
- camera URL / IP
- local filesystem paths
- participant / patient / subject identifiers or names
- email, API credentials

This module enforces the whitelist (``build_input``), produces a canonical,
deterministic evidence JSON, and its SHA-256 ``evidence_digest`` used for
reproducibility and the explanation cache. It also defines the expected
structured output schema and a prohibited-claim detector used to reject unsafe
remote output.

The explainer never calculates a primary score; there is no clinical score.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

INPUT_SCHEMA_VERSION = "1.0"

# Whitelist of top-level evidence keys allowed to reach the explainer. Only
# structured, non-identifying evidence is included.
ALLOWED_INPUT_KEYS = {
    "exercise",
    "data_origin",
    "processing_mode",
    "quality",
    "primary_outcomes",
    "control_factors",
    "descriptive_kinematics",
    "session_descriptors",
    "temporal_analysis",
    "method_provenance",
    "limitations",
}

# Expected structured explanation output.
OUTPUT_SCHEMA_KEYS = ("summary", "observations", "limitations", "safety_note")

# ── Recursive provider privacy boundary (items 1/28) ─────────────────────────
# Explicit normalized names + careful bounded suffix checks (*_path, *_url), so
# legitimate keys like frame_index / sequence_key / landmark are never rejected.
FORBIDDEN_IDENTITY_KEYS = {
    "patient", "patient_id", "patient_name",
    "participant_id", "participant_name",
    "subject_id", "subject_name",
    "email",
}

FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key", "token", "secret", "password", "authorization",
}

FORBIDDEN_RAW_SOURCE_KEYS = {
    "camera_url", "camera_source",
    "video_path", "image_path", "file_path", "local_path", "absolute_path",
    "raw_video", "raw_frame", "image_bytes", "frame_bytes",
}

REJECTED_SUFFIXES = ("_path", "_url")


def _is_forbidden_nested_key(key: Any) -> bool:
    name = str(key).strip().lower()
    if name in FORBIDDEN_IDENTITY_KEYS:
        return True
    if name in FORBIDDEN_CREDENTIAL_KEYS:
        return True
    if name in FORBIDDEN_RAW_SOURCE_KEYS:
        return True
    return name.endswith(REJECTED_SUFFIXES)


def prune_sensitive_fields(obj: Any) -> Any:
    """Recursively drop sensitive keys from nested dict/list structures.

    Identity, credential, raw-source, and ``*_path`` / ``*_url`` keys are
    removed at every nesting level so they can never reach a provider. Benign
    keys (``frame_index``, ``sequence_key``, ``landmark``) are preserved.
    """
    if isinstance(obj, dict):
        return {
            key: prune_sensitive_fields(value)
            for key, value in obj.items()
            if not _is_forbidden_nested_key(key)
        }
    if isinstance(obj, (list, tuple)):
        return [prune_sensitive_fields(item) for item in obj]
    return obj


def build_input(evidence: dict) -> dict:
    """Return whitelisted, recursively privacy-pruned evidence for explanation.

    Only keys in ``ALLOWED_INPUT_KEYS`` survive the top-level whitelist, then
    every nested dict/list is recursively pruned of identity/credential/
    raw-path fields. This runs automatically inside the boundary, so a developer
    never has to remember a separate validator. Sensitive keys are dropped
    (never sent); they are treated as absent.
    """
    if not isinstance(evidence, dict):
        raise ValueError("explainer input must be a structured dict")
    top_level = {
        k: v for k, v in evidence.items()
        if k in ALLOWED_INPUT_KEYS and v is not None
    }
    return prune_sensitive_fields(top_level)


def has_sensitive_fields(evidence: dict) -> bool:
    """True if the (whitelisted) evidence still contains a sensitive nested key."""
    return prune_sensitive_fields(evidence) != evidence


def canonical_json(evidence_input: dict) -> str:
    """Deterministic canonical JSON of a whitelisted evidence input."""
    return json.dumps(evidence_input, sort_keys=True, separators=(",", ":"), allow_nan=False)


def evidence_digest(evidence_input: dict) -> str:
    """SHA-256 digest of the canonical evidence JSON (reproducibility)."""
    return hashlib.sha256(canonical_json(evidence_input).encode("utf-8")).hexdigest()


def validate_output_shape(output: Any) -> bool:
    """True if ``output`` is a dict with the expected string fields."""
    if not isinstance(output, dict):
        return False
    for key in OUTPUT_SCHEMA_KEYS:
        if key not in output:
            return False
    for key in ("summary", "safety_note"):
        if not isinstance(output.get(key), str):
            return False
    for list_key in ("observations", "limitations"):
        value = output.get(list_key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            return False
    return True


# Prohibited clinical/medical claims in explained output.
PROHIBITED_CLAIM_PATTERNS = [
    re.compile(r"\bdiagnos", re.IGNORECASE),
    re.compile(r"\bclinical(ly)?\s+valid", re.IGNORECASE),
    re.compile(r"\bmedically\s+correct", re.IGNORECASE),
    re.compile(r"\bmedically\s+incorrect", re.IGNORECASE),
    re.compile(r"\btreatment(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bprescription", re.IGNORECASE),
    re.compile(r"\bhealthy\b", re.IGNORECASE),
    re.compile(r"\bdisease", re.IGNORECASE),
    re.compile(r"\brisk\s+of", re.IGNORECASE),
    re.compile(r"\brehabilitation\s+(?:is|was)\s+successful", re.IGNORECASE),
    re.compile(r"\bscore\s+of\s+\d", re.IGNORECASE),
    re.compile(r"\bclinically\s+reliab", re.IGNORECASE),
    # Direct movement/exercise judgements + rehabilitation performance claims.
    re.compile(r"\bmovement\s+is\s+(?:correct|incorrect|normal|abnormal|good|bad)\b", re.IGNORECASE),
    re.compile(r"\b(?:exercise|squat)\s+is\s+(?:correct|incorrect|normal|abnormal|good|bad)\b", re.IGNORECASE),
    re.compile(r"\b(?:good|bad)\s+rehabilitation\s+performance\b", re.IGNORECASE),
    re.compile(r"\bclinical\s+improvement\b", re.IGNORECASE),
    re.compile(r"\bquality\s+of\s+\d+\s*/\s*10\b", re.IGNORECASE),
]


def contains_prohibited_claim(output: Any) -> bool:
    """True if the explanation output contains a prohibited clinical claim."""
    if not isinstance(output, dict):
        return True
    haystack = " ".join(
        str(output.get(k, "")) for k in ("summary", "safety_note")
    ) + " " + " ".join(str(item) for k in ("observations", "limitations")
                       for item in (output.get(k) if isinstance(output.get(k), list) else []))
    return any(p.search(haystack) for p in PROHIBITED_CLAIM_PATTERNS)

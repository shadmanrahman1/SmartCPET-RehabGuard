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

# Explicitly REJECTED fields even if nested (defense in depth).
REJECTED_FIELD_HINTS = ("video", "camera", "image", "frame", "path", "url",
                        "email", "ip", "key", "token", "secret", "password")


def reject_evidence_raw(*, evidence: Any) -> None:
    """Raise ValueError if NON-whitelisted raw/identifying evidence fields exist.

    Whitelisted schema keys (see ``ALLOWED_INPUT_KEYS``) are always allowed; the
    scan targets other (non-whitelisted) fields whose names hint at raw video,
    paths, identity, or credentials. This is a defensive guard before the
    whitelist reduction in :func:`build_input`.
    """
    if not isinstance(evidence, dict):
        raise ValueError("explainer input must be a structured dict")
    for key in evidence:
        if key in ALLOWED_INPUT_KEYS:
            continue
        hint = str(key).lower()
        if any(h in hint for h in REJECTED_FIELD_HINTS):
            raise ValueError(f"raw/identifying field not allowed for explanation: {key}")


def build_input(evidence: dict) -> dict:
    """Return the whitelisted, non-identifying evidence for explanation.

    Only keys in ``ALLOWED_INPUT_KEYS`` are kept; everything else (raw video,
    paths, identity, credentials) is DROPPED so it can never reach a provider.
    Strict rejection can be enforced explicitly via :func:`reject_evidence_raw`.
    """
    if not isinstance(evidence, dict):
        raise ValueError("explainer input must be a structured dict")
    return {
        k: v for k, v in evidence.items()
        if k in ALLOWED_INPUT_KEYS and v is not None
    }


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

"""
Tests for the bounded explainer layer (Sprint C C6-C11).

Mock the remote OpenRouter provider entirely; NO real API call. Covers template
fallback, missing key, rate limit, invalid JSON, prohibited claims, valid
response acceptance, audit trail (no key), evidence digest stability, and the
explanation cache.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from explanation_schema import build_input, evidence_digest  # noqa: E402
from evidence_explainer import template_explain  # noqa: E402
from openrouter_explainer import (  # noqa: E402
    SYSTEM_INSTRUCTION,
    OpenRouterExplainer,
    explain,
)
from unittest import mock  # noqa: E402


def _evidence():
    return {
        "schema_version": "1.0",
        "exercise": "kimore_ex5_squat",
        "data_origin": "REAL_VIDEO_MEDIAPIPE",
        "processing_mode": "live_mediapipe",
        "quality": {"available": True, "left_po_available": True, "right_po_available": True},
        "primary_outcomes": {"left_knee_sagittal_deg": 150.0, "right_knee_sagittal_deg": 148.0},
        "session_descriptors": {"left_knee_rom_deg": 40.0, "right_knee_rom_deg": 38.0},
    }


def _ok_payload(content):
    return {"choices": [{"message": {"content": json.dumps(content)}}], "model": "provider/model"}


class TemplateExplainerTests(unittest.TestCase):
    def test_template_explain_structure(self):
        out = template_explain(_evidence())
        self.assertEqual(set(out), {"summary", "observations", "limitations", "safety_note"})
        self.assertIn("not a clinical assessment", out["safety_note"])

    def test_missing_evidence_explanation(self):
        ev = {
            "quality": {"available": False, "left_po_available": False, "right_po_available": True},
            "primary_outcomes": {"left_knee_sagittal_deg": None, "right_knee_sagittal_deg": 140.0},
        }
        out = template_explain(ev)
        text = " ".join(out["observations"]) + out["summary"]
        self.assertIn("left", text.lower())

    def test_no_prohibited_claims(self):
        from explanation_schema import contains_prohibited_claim
        out = template_explain(_evidence())
        self.assertFalse(contains_prohibited_claim(out))


class InputContractTests(unittest.TestCase):
    def test_whitelist_removes_raw_and_identity(self):
        ev = {
            "schema_version": "1.0",
            "quality": {"available": True},
            "video_path": "/tmp/Patient_A.mp4",
            "camera_url": "http://secret:key@host",
            "participant_name": "Alice",
        }
        reduced = build_input(ev)
        for banned in ("video_path", "camera_url", "participant_name"):
            self.assertNotIn(banned, reduced)

    def test_nested_camera_url_rejected(self):
        ev = {"quality": {"available": True, "camera_url": "http://cam"}}
        pruned = build_input(ev)
        self.assertNotIn("camera_url", pruned["quality"])

    def test_nested_video_path_rejected(self):
        ev = {"quality": {"available": True, "video_path": "/tmp/x.mp4"}}
        pruned = build_input(ev)
        self.assertNotIn("video_path", pruned["quality"])

    def test_nested_api_key_and_token_rejected(self):
        ev = {"quality": {"available": True, "api_key": "k", "token": "t"}}
        pruned = build_input(ev)
        self.assertNotIn("api_key", pruned["quality"])
        self.assertNotIn("token", pruned["quality"])

    def test_nested_identity_rejected(self):
        ev = {"method_provenance": {"owner": {"patient_name": "Alice", "participant_id": "7", "email": "e@x"}}}
        pruned = build_input(ev)
        nested = str(pruned["method_provenance"])
        self.assertNotIn("patient_name", nested)
        self.assertNotIn("participant_id", nested)
        self.assertNotIn("email", nested)

    def test_legitimate_keys_not_false_rejected(self):
        ev = {"quality": {"available": True, "frame_index": 5, "landmark": "left_hip", "sequence_key": "abc123"}}
        pruned = build_input(ev)
        q = pruned["quality"]
        self.assertEqual(q["frame_index"], 5)
        self.assertEqual(q["landmark"], "left_hip")
        self.assertEqual(q["sequence_key"], "abc123")

    def test_list_nested_pruned(self):
        ev = {"limitations": ["note", {"raw_frame": "bytes", "file_path": "/x"}]}
        pruned = build_input(ev)
        self.assertNotIn("raw_frame", str(pruned))
        self.assertNotIn("file_path", str(pruned))

    def test_evidence_digest_stable(self):
        self.assertEqual(evidence_digest({"a": 1, "b": 2}), evidence_digest({"b": 2, "a": 1}))

    def test_build_input_requires_dict(self):
        with self.assertRaises(ValueError):
            build_input("not a dict")


class ProviderPrivacyBoundaryTests(unittest.TestCase):
    """Nested-sensitive input must never trigger a remote provider call."""

    def test_no_remote_call_after_sensitive_input(self):
        exp = OpenRouterExplainer(mode="openrouter", api_key="sk-test-abcdef123", model="m1",
                                  base_url="https://openrouter.ai/api/v1")
        evidence = {"quality": {"available": True, "api_key": "sk-secret", "camera_url": "http://cam"}}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("must not call remote")):
            audit = exp.explain(evidence)
        self.assertEqual(audit["status"], "INPUT_CONTAINS_SENSITIVE_NO_REMOTE")
        self.assertIsNone(audit["provider"])


class OpenRouterExplainerTests(unittest.TestCase):
    def _explainer(self, mode="openrouter", api_key="sk-test-abcdef123", model="m1"):
        return OpenRouterExplainer(mode=mode, api_key=api_key, model=model,
                                   base_url="https://openrouter.ai/api/v1")

    def test_default_mode_is_template(self):
        self.assertEqual(OpenRouterExplainer(mode=None).mode, "template")

    def test_provider_rejects_arbitrary_host(self):
        with self.assertRaises(ValueError):
            OpenRouterExplainer(mode="openrouter", api_key="k", model="m", base_url="https://example.test/v1")
        with self.assertRaises(ValueError):
            OpenRouterExplainer(mode="openrouter", api_key="k", model="m", base_url="http://openrouter.ai/v1")

    def test_missing_key_uses_separate_config_status(self):
        exp = OpenRouterExplainer(mode="openrouter", api_key="", model="m1",
                                  base_url="https://openrouter.ai/api/v1")
        self.assertFalse(exp._remote_ready)
        audit = exp.explain(_evidence())
        self.assertEqual(audit["status"], "OPENROUTER_NOT_CONFIGURED")
        self.assertEqual(audit["explainer_mode"], "openrouter")

    def test_valid_response_accepted_and_model_recorded(self):
        exp = self._explainer()
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = json.dumps(
                _ok_payload({"summary": "ok", "observations": ["x"],
                             "limitations": ["y"], "safety_note": "desc research"})
            ).encode()
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OK")
            self.assertEqual(audit["provider"], "openrouter")
            self.assertEqual(audit["requested_model"], "m1")
            self.assertEqual(audit["returned_model"], "provider/model")
            self.assertEqual(audit["output"]["summary"], "ok")
        # API key must never be serialized in the audit.
        self.assertNotIn(exp.api_key, json.dumps(audit))

    def test_invalid_json_falls_back(self):
        exp = self._explainer()
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = b"not json"
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OPENROUTER_INVALID_RESPONSE")
            self.assertTrue(audit["output"]["observations"])  # template fallback

    def test_rate_limit_falls_back(self):
        import urllib.error
        exp = self._explainer()
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                "url", 429, "rate", None, None)):
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OPENROUTER_RATE_LIMITED")

    def test_network_failure_falls_back(self):
        import urllib.error
        exp = self._explainer()
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OPENROUTER_UNAVAILABLE")

    def test_prohibited_claim_rejected(self):
        exp = self._explainer()
        response = {"summary": "patient is healthy", "observations": [],
                    "limitations": [], "safety_note": "note"}
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = json.dumps(_ok_payload(response)).encode()
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OPENROUTER_INVALID_RESPONSE")

    def test_cache_hit_reuses(self):
        exp = self._explainer()
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = json.dumps(
                _ok_payload({"summary": "s", "observations": ["o"],
                             "limitations": ["l"], "safety_note": "remote says x"})
            ).encode()
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            first = exp.explain(_evidence())
            self.assertEqual(first["status"], "OK")
            self.assertEqual(first["returned_model"], "provider/model")
        # Second call: same digest -> cache hit, no new remote call, metadata kept.
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("should not call")):
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "CACHE_HIT")
            self.assertEqual(audit["provider"], "openrouter")
            self.assertEqual(audit["requested_model"], "m1")
            self.assertEqual(audit["returned_model"], "provider/model")

    def test_safety_note_forced_on_remote_output(self):
        exp = self._explainer()
        response = {"summary": "s", "observations": ["o"], "limitations": ["l"],
                    "safety_note": "UNTRUSTED remote safety text"}
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = json.dumps(_ok_payload(response)).encode()
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OK")
            self.assertIn("not a clinical assessment", audit["output"]["safety_note"])
            self.assertNotIn("UNTRUSTED remote safety text", audit["output"]["safety_note"])

    def test_rate_limit_not_cached_and_retries_next(self):
        import urllib.error
        exp = self._explainer()
        # First call: rate limited.
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                "url", 429, "rate", None, None)):
            audit = exp.explain(_evidence())
            self.assertEqual(audit["status"], "OPENROUTER_RATE_LIMITED")
        # Next explicit request should RETRY OpenRouter (not served from a cache).
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = json.dumps(
                _ok_payload({"summary": "ok", "observations": ["o"],
                             "limitations": ["l"], "safety_note": "n"})
            ).encode()
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            audit2 = exp.explain(_evidence())
            self.assertEqual(audit2["status"], "OK")
            urlopen.assert_called()  # remote was actually retried

    def test_force_bypasses_cache(self):
        exp = self._explainer()
        content = {"summary": "s", "observations": ["o"],
                   "limitations": ["l"], "safety_note": "n"}
        with mock.patch("urllib.request.urlopen") as urlopen:
            ctx = mock.MagicMock()
            ctx.__enter__().read.return_value = json.dumps(_ok_payload(content)).encode()
            ctx.__exit__.return_value = False
            urlopen.return_value = ctx
            exp.explain(_evidence())
        # force=True must attempt a remote call even for a cached digest.
        with mock.patch("urllib.request.urlopen") as urlopen2:
            ctx2 = mock.MagicMock()
            ctx2.__enter__().read.return_value = json.dumps(_ok_payload(content)).encode()
            ctx2.__exit__.return_value = False
            urlopen2.return_value = ctx2
            exp.explain(_evidence(), force=True)
            urlopen2.assert_called()

    def test_system_instruction_bounded(self):
        self.assertIn("not a clinical assessment", SYSTEM_INSTRUCTION)
        self.assertIn("Do not diagnose", SYSTEM_INSTRUCTION)

    def test_explain_convenience_uses_template_without_key(self):
        audit = explain(_evidence())
        self.assertEqual(audit["status"], "TEMPLATE")


if __name__ == "__main__":
    unittest.main()

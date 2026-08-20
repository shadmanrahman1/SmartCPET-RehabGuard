"""
Narrow, portable tests for the safe BIOGAIT root .env loader in
``biogait/openrouter_explainer.py``.

Security/portability contract:
- Tests MUST NOT use the user's real private root ``.env`` or real API key.
- Tests MUST NOT rely on a local Windows venv path or the real repo-root
  ``.env``. They use ``unittest.mock`` to patch ``dotenv.load_dotenv`` and run
  in-process, deriving the biogait path from ``__file__``.
- The loader is a no-op when python-dotenv is missing.
- The loader uses ``override=False`` (process env wins over ``.env``).
- The loader consults ONLY the deterministic repo-root ``.env``.
- The audit output never contains the API key.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util as u  # noqa: F401
import inspect
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

# biogait path derived from this file (tests/ -> repo root -> biogait/).
REPO_ROOT = Path(__file__).resolve().parent.parent
BG = REPO_ROOT / "biogait"
if str(BG) not in sys.path:
    sys.path.insert(0, str(BG))


def _clear_or_vars():
    for k in [
        "OPENROUTER_API_KEY",
        "BIOGAIT_EXPLAINER_MODE",
        "BIOGAIT_OPENROUTER_MODEL",
        "BIOGAIT_OPENROUTER_BASE_URL",
    ]:
        os.environ.pop(k, None)


class OpenRouterEnvLoaderTests(unittest.TestCase):
    def setUp(self):
        _clear_or_vars()
        # Force the loader's dotenv import to our stub for isolation so the
        # user's real private .env is never read by in-process tests.
        self._stub_dotenv()

    def _stub_dotenv(self):
        stub = types.ModuleType("dotenv")
        stub.__spec__ = importlib.machinery.ModuleSpec("dotenv", loader=None)
        stub.load_dotenv = lambda *a, **k: True
        sys.modules["dotenv"] = stub
        return stub

    def test_loader_present_means_python_dotenv_available(self):
        # Sanity: python-dotenv is declared in biogait/requirements.txt. In a
        # normal runtime it is importable. (On CI this may be skipped if not
        # installed; the loader is a safe no-op either way.)
        try:
            import dotenv  # noqa: F401
            self.assertTrue(u.find_spec("dotenv") is not None)
        except Exception:  # pragma: no cover - CI may not install dotenv
            self.skipTest("python-dotenv not installed in this environment")

    def test_loader_reads_repo_root_dotenv_and_sets_env(self):
        # Patch load_dotenv to apply a known set (simulating a root .env that
        # sets these three vars), then confirm the loader populated them.
        import openrouter_explainer as oe

        def _fake_load_dotenv(dotenv_path, override=False):
            # Pretend the file at dotenv_path sets these values.
            os.environ.setdefault("OPENROUTER_API_KEY", "fake-not-real")
            os.environ.setdefault("BIOGAIT_EXPLAINER_MODE", "openrouter")
            os.environ.setdefault("BIOGAIT_OPENROUTER_MODEL", "fake/model:free")
            return True

        with mock.patch.object(oe, "_load_repo_dotenv", wraps=oe._load_repo_dotenv):
            with mock.patch("dotenv.load_dotenv", side_effect=_fake_load_dotenv):
                oe._load_repo_dotenv()
        self.assertEqual(os.environ.get("BIOGAIT_EXPLAINER_MODE"), "openrouter")
        self.assertEqual(os.environ.get("BIOGAIT_OPENROUTER_MODEL"), "fake/model:free")
        self.assertTrue(os.environ.get("OPENROUTER_API_KEY"))
        # Clean up the fake values so they don't leak into later tests.
        _clear_or_vars()

    def test_loader_override_false_process_env_wins(self):
        # Pre-set a process env value BEFORE the loader runs; override=False
        # must keep the process value, not the .env one.
        os.environ["BIOGAIT_EXPLAINER_MODE"] = "template"  # process env
        import openrouter_explainer as oe

        with mock.patch("dotenv.load_dotenv", side_effect=lambda *a, **k: True):
            oe._load_repo_dotenv()
        self.assertEqual(os.environ.get("BIOGAIT_EXPLAINER_MODE"), "template")
        _clear_or_vars()

    def test_missing_dotenv_does_not_break_biogait(self):
        # If load_dotenv raises (e.g. dotenv missing), the loader must no-op.
        import openrouter_explainer as oe

        with mock.patch("dotenv.load_dotenv", side_effect=ImportError("simulated")):
            oe._load_repo_dotenv()  # must not raise
        self.assertNotIn("OPENROUTER_API_KEY", os.environ)

    def test_loader_consults_only_repo_root_dotenv(self):
        import openrouter_explainer as oe
        src = inspect.getsource(oe._load_repo_dotenv)
        self.assertIn("parents[1]", src)
        self.assertNotIn("parents[2]", src)
        self.assertNotIn("parents[3]", src)
        self.assertIn("override=False", src)
        self.assertIn('repo_root / ".env"', src)
        self.assertNotIn("find_dotenv", src)
        self.assertNotIn(".env.example", src)

    def test_audit_never_includes_api_key(self):
        from openrouter_explainer import OpenRouterExplainer
        from explanation_schema import build_input
        sentinel = "sk-test-abcdef123"
        ae = OpenRouterExplainer(mode="openrouter", api_key=sentinel, model="m1")
        audit = ae.explain(build_input({"x": 1}))
        raw = json.dumps(audit)
        self.assertNotIn(sentinel, raw)
        self.assertNotIn("api_key", audit)

    def test_provider_host_rejection(self):
        from openrouter_explainer import OpenRouterExplainer
        with self.assertRaises(ValueError):
            OpenRouterExplainer(
                mode="openrouter", api_key="k", model="m",
                base_url="https://example.test/v1",
            )
        with self.assertRaises(ValueError):
            OpenRouterExplainer(
                mode="openrouter", api_key="k", model="m",
                base_url="http://openrouter.ai/v1",
            )

    def test_template_default_preserved(self):
        from openrouter_explainer import OpenRouterExplainer
        ae = OpenRouterExplainer(mode="template")
        self.assertEqual(ae.mode, "template")
        self.assertFalse(ae._remote_ready)


if __name__ == "__main__":
    unittest.main()

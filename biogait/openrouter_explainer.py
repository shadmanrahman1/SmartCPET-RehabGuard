"""Optional remote BioGait explainer via OpenRouter (Sprint C, C8-C11).

BioGait does NOT run a local medical LLM (no transformers / MedGemma / Ollama /
llama.cpp / local model). Remote explanation (when explicitly configured) uses
the OpenRouter API; the core runtime works WITHOUT it.

Modes (BIOGAIT_EXPLAINER_MODE):
  disabled   -> template fallback only, no remote
  template   -> deterministic template explainer (DEFAULT)
  openrouter -> optional remote explanation via OpenRouter

Configuration (environment variables ONLY; no committed secrets):
  OPENROUTER_API_KEY           required for openrouter mode
  BIOGAIT_OPENROUTER_MODEL     explicit model slug (e.g. a current OpenRouter
                               model; NOT hard-coded to MedGemma)
  BIOGAIT_OPENROUTER_BASE_URL  optional; default https://openrouter.ai/api/v1

Policy:
- The remote model receives ONLY whitelisted structured evidence (never raw
  video/frames/paths/identity/credentials).
- Strict JSON output contract is validated; malformed/unsafe output is rejected
  and the deterministic template explainer is used.
- Any failure (missing key, network, HTTP, rate limit, timeout, invalid JSON,
  model unavailable) falls back to template with a neutral status
  (OPENROUTER_UNAVAILABLE / OPENROUTER_RATE_LIMITED /
  OPENROUTER_INVALID_RESPONSE). Never block capture; never called per frame.
- Explanation cache: same evidence_digest reuses a prior explanation within the
  session unless force=True.
- Audit trail records provider/model/digest/timestamp/output but NEVER the API
  key, endpoint credentials, or raw prompt with secrets.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from explanation_schema import (
    INPUT_SCHEMA_VERSION,
    build_input,
    contains_prohibited_claim,
    evidence_digest,
    validate_output_shape,
)
from evidence_explainer import SAFETY_NOTE, template_explain

ENV_MODE = "BIOGAIT_EXPLAINER_MODE"
ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "BIOGAIT_OPENROUTER_MODEL"
ENV_BASE_URL = "BIOGAIT_OPENROUTER_BASE_URL"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

VALID_MODES = ("disabled", "template", "openrouter")

SYSTEM_INSTRUCTION = (
    "You summarize only the supplied structured BioGait movement evidence. "
    "Do not invent values. Do not invent missing measurements. Do not diagnose "
    "disease. Do not produce treatment recommendations. Do not classify the "
    "movement as medically correct or incorrect. Do not create a "
    "rehabilitation score. Do not claim the result is clinically validated. "
    "Clearly distinguish descriptive evidence from reference-derived and "
    "engineering-adapted methods. If evidence is missing, explicitly state "
    "that it is unavailable. Your output is a research-evidence explanation, "
    "not a clinical assessment. Respond ONLY with a JSON object with keys "
    "summary, observations, limitations, safety_note."
)

USER_TEMPLATE = (
    "Here is neutral structured BioGait research evidence (no clinical score):\n"
    "{evidence}\n"
    "Return a JSON object: {{\"summary\": str, \"observations\": [str], "
    "\"limitations\": [str], \"safety_note\": str}}."
)


def _env_config(api_key=None, model=None, base_url=None):
    mode = os.environ.get(ENV_MODE, "template") or "template"
    if mode not in VALID_MODES:
        mode = "template"
    key = api_key if api_key is not None else os.environ.get(ENV_API_KEY)
    mdl = model if model is not None else os.environ.get(ENV_MODEL)
    base = base_url if base_url is not None else os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)
    return mode, key, mdl, base


class OpenRouterExplainer:
    """Bounded explainer: disabled / template / openrouter."""

    def __init__(
        self,
        mode: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        resolved_mode, key, mdl, base = _env_config(api_key, model, base_url)
        self.mode = mode or resolved_mode
        if self.mode not in VALID_MODES:
            self.mode = "template"
        self.api_key = key
        self.model = mdl
        self.base_url = (base or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = float(timeout)
        # Remote is only attempted when explicitly configured with a key+model.
        self._remote_ready = (
            self.mode == "openrouter"
            and bool(self.api_key)
            and bool(self.model)
        )
        self._cache: dict[str, dict] = {}

    def _user_message(self, evidence_input: dict) -> str:
        return USER_TEMPLATE.format(
            evidence=json.dumps(evidence_input, sort_keys=True, ensure_ascii=False)
        )

    def _call_remote(self, evidence_input: dict) -> tuple[str, Optional[dict]]:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": self._user_message(evidence_input)},
            ],
        }
        url = f"{self.base_url}/chat/completions"
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                return "OPENROUTER_RATE_LIMITED", None
            return "OPENROUTER_UNAVAILABLE", None
        except Exception:  # noqa: BLE001 - network/timeout -> neutral fallback
            return "OPENROUTER_UNAVAILABLE", None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return "OPENROUTER_INVALID_RESPONSE", None

        try:
            message = payload["choices"][0]["message"]
            content = message.get("content")
            returned_model = payload.get("model")
            if isinstance(content, str):
                output = json.loads(content)
            elif isinstance(content, dict):
                output = content
            else:
                return "OPENROUTER_INVALID_RESPONSE", None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return "OPENROUTER_INVALID_RESPONSE", None

        if not validate_output_shape(output) or contains_prohibited_claim(output):
            return "OPENROUTER_INVALID_RESPONSE", None

        return "OK", {"output": output, "returned_model": returned_model}

    def explain(self, evidence: dict, force: bool = False) -> dict:
        """Explain structured evidence; returns an explanation + audit dict."""
        try:
            evidence_input = build_input(evidence)
            digest = evidence_digest(evidence_input)
        except ValueError as exc:
            return {
                "explainer_mode": "template",
                "provider": None,
                "requested_model": None,
                "returned_model": None,
                "input_schema_version": INPUT_SCHEMA_VERSION,
                "evidence_digest": None,
                "timestamp": _now(),
                "status": "INPUT_REJECTED",
                "output": template_explain({"quality": {}}),
                "note": f"explainer input rejected: {exc}",
            }

        output = template_explain(evidence_input)
        status = "TEMPLATE"
        provider = None
        requested_model = None
        returned_model = None

        if not force and digest in self._cache:
            output = self._cache[digest]
            status = "CACHE_HIT"
        elif self._remote_ready:
            status_remote, remote_result = self._call_remote(evidence_input)
            provider = "openrouter"
            requested_model = self.model
            if status_remote == "OK" and remote_result is not None:
                output = remote_result["output"]
                returned_model = remote_result.get("returned_model")
                self._cache[digest] = output
                status = "OK"
            else:
                # Fallback to deterministic template; keep neutral status.
                status = status_remote
                self._cache.setdefault(digest, template_explain(evidence_input))
                output = template_explain(evidence_input)
        else:
            self._cache.setdefault(digest, output)

        return {
            "explainer_mode": self.mode,
            "provider": provider,
            "requested_model": requested_model,
            "returned_model": returned_model,
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "evidence_digest": digest,
            "timestamp": _now(),
            "status": status,
            "output": output,
        }


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def make_explainer(
    mode: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> OpenRouterExplainer:
    return OpenRouterExplainer(mode=mode, api_key=api_key, model=model, base_url=base_url)


def explain(evidence: dict, force: bool = False) -> dict:
    """Convenience: explain evidence using the default configured explainer."""
    return make_explainer().explain(evidence, force=force)

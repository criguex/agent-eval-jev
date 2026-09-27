from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

GATEWAY_URL = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
DIRECT_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
PRICE_PER_MTOK = 0.042
PINNED_PROVIDER = "typesafe-ai"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "jev"


class JevError(Exception):
    pass


class MissingFixture(JevError):
    pass


@dataclass
class JevResponse:
    answers: dict
    model: str
    input_tokens: int
    cost_usd: float
    latency_ms: float
    attempts: int
    provider: str | None = None


def normalize_answer(raw: dict) -> dict:
    kind = raw.get("type")
    if kind in ("noul", "boolean"):
        value = raw.get("noul", raw.get("probability"))
        if value is None:
            raise JevError(f"noul answer without probability: {raw}")
        return {"type": "noul", "noul": float(value)}
    if kind in ("choice", "score"):
        return raw
    raise JevError(f"unknown answer type: {raw}")


def request_key(body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _credentials() -> tuple[str, str] | None:
    if os.environ.get("TYPESAFE_API_KEY"):
        return DIRECT_URL, os.environ["TYPESAFE_API_KEY"]
    if os.environ.get("AI_GATEWAY_API_KEY"):
        return GATEWAY_URL, os.environ["AI_GATEWAY_API_KEY"]
    return None


def live_available() -> bool:
    return _credentials() is not None


def _post(url: str, key: str, body: dict, max_attempts: int = 80) -> tuple[dict, float, int]:
    data = json.dumps(body).encode("utf-8")
    delay = 1.0
    last = ""
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, (time.perf_counter() - started) * 1000, attempt
        except urllib.error.HTTPError as error:
            last = f"HTTP {error.code}: {error.read().decode('utf-8', 'replace')[:500]}"
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise JevError(last) from error
        except (urllib.error.URLError, TimeoutError) as error:
            last = str(error)
        time.sleep(delay * (0.5 + random.random()))
        delay = min(delay * 1.5, 6)
    raise JevError(f"gave up after {max_attempts} attempts: {last}")


class JevClient:
    def __init__(self, mode: str | None = None, fixtures: Path = FIXTURES, route: str | None = PINNED_PROVIDER):
        self.mode = mode or os.environ.get("JEV_MODE", "replay")
        self.fixtures = fixtures
        self.route = route
        if self.mode not in ("replay", "live", "record"):
            raise ValueError(f"JEV_MODE must be replay, live or record, got {self.mode}")

    def _path(self, body: dict) -> Path:
        keyed = {**body, "route": self.route} if self.route else body
        return self.fixtures / f"{request_key(keyed)}.json"

    def recorded(self, state, questions: dict) -> list[JevResponse]:
        path = self._path(self._body(state, questions))
        if not path.exists():
            return []
        return [JevResponse(**r) for r in json.loads(path.read_text())["responses"]]

    @staticmethod
    def _body(state, questions: dict) -> dict:
        return {"model": MODEL, "state": state, "questions": questions}

    def ask(self, state, questions: dict, repeat: int = 0) -> JevResponse:
        body = self._body(state, questions)
        path = self._path(body)
        stored = json.loads(path.read_text()) if path.exists() else {"request": body, "responses": []}
        if self.mode == "replay" or (self.mode == "record" and repeat < len(stored["responses"])):
            if repeat >= len(stored["responses"]):
                raise MissingFixture(f"no recorded Jev response #{repeat} for {path.name}; run with JEV_MODE=record")
            return JevResponse(**stored["responses"][repeat])
        credentials = _credentials()
        if credentials is None:
            raise JevError(f"JEV_MODE={self.mode} needs AI_GATEWAY_API_KEY or TYPESAFE_API_KEY")
        url, key = credentials
        sent = body
        if url == GATEWAY_URL and self.route:
            sent = {**body, "providerOptions": {"gateway": {"only": [self.route]}}}
        payload, latency_ms, attempts = _post(url, key, sent)
        if "answers" not in payload:
            raise JevError(f"unexpected Jev payload: {json.dumps(payload)[:500]}")
        answers = {k: normalize_answer(v) for k, v in payload["answers"].items()}
        usage = payload.get("usage") or {}
        tokens = int(usage.get("input_tokens") or 0)
        gateway = (payload.get("provider_metadata") or payload.get("providerMetadata") or {}).get("gateway") or {}
        cost = float(gateway["cost"]) if gateway.get("cost") is not None else tokens * PRICE_PER_MTOK / 1e6
        provider = (gateway.get("routing") or {}).get("finalProvider") or ("typesafe-ai" if url == DIRECT_URL else None)
        response = JevResponse(answers, payload.get("model", MODEL), tokens, cost, round(latency_ms, 1), attempts, provider)
        if self.mode == "record":
            stored["responses"].append(response.__dict__)
            self.fixtures.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(stored, indent=1, ensure_ascii=False) + "\n")
        return response

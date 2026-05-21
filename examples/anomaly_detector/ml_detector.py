"""Bundle-feature anomaly detector for EmION experiments."""

from __future__ import annotations

import argparse
import math
import random
import time
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import Body, FastAPI

try:
    from sklearn.ensemble import IsolationForest
except ImportError:  # pragma: no cover - optional dependency
    IsolationForest = None


FEATURE_ORDER = [
    "bundle_size",
    "inter_arrival_time_ms",
    "hop_count",
    "ttl_seconds",
    "queue_delay_ms",
    "retransmission_count",
    "contact_duration_s",
    "route_length",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_features(metadata: Dict[str, Any]) -> Dict[str, float]:
    bundle_features = metadata.get("bundle_features") or {}
    route_forecast = metadata.get("route_forecast") or {}
    predicted_path = route_forecast.get("predicted_path") or route_forecast.get("current_path") or []
    return {
        "bundle_size": _safe_float(bundle_features.get("bundle_size", metadata.get("payload_size", metadata.get("size", 0)))),
        "inter_arrival_time_ms": _safe_float(bundle_features.get("inter_arrival_time_ms", 0.0)),
        "hop_count": _safe_float(bundle_features.get("hop_count", max(len(predicted_path) - 1, 0))),
        "ttl_seconds": _safe_float(bundle_features.get("ttl_seconds", metadata.get("ttl_seconds", 300))),
        "queue_delay_ms": _safe_float(bundle_features.get("queue_delay_ms", 0.0)),
        "retransmission_count": _safe_float(bundle_features.get("retransmission_count", metadata.get("retransmission_count", 0))),
        "contact_duration_s": _safe_float(bundle_features.get("contact_duration_s", 0.0)),
        "route_length": _safe_float(bundle_features.get("route_length", len(predicted_path))),
    }


def vectorize(features: Dict[str, float]) -> np.ndarray:
    return np.asarray([features.get(name, 0.0) for name in FEATURE_ORDER], dtype=np.float64)


class RollingFallbackDetector:
    """Lightweight anomaly detector used when scikit-learn is unavailable."""

    def __init__(self) -> None:
        self.history: List[np.ndarray] = [vectorize(sample) for sample in self._seed_samples()]

    def _seed_samples(self) -> List[Dict[str, float]]:
        rng = random.Random(7)
        samples = []
        for _ in range(64):
            samples.append({
                "bundle_size": rng.uniform(128, 1024),
                "inter_arrival_time_ms": rng.uniform(20, 400),
                "hop_count": rng.uniform(1, 4),
                "ttl_seconds": rng.uniform(120, 600),
                "queue_delay_ms": rng.uniform(0, 50),
                "retransmission_count": rng.uniform(0, 1),
                "contact_duration_s": rng.uniform(30, 600),
                "route_length": rng.uniform(2, 5),
            })
        return samples

    def score(self, vector: np.ndarray) -> tuple[float, str]:
        matrix = np.vstack(self.history)
        mean = matrix.mean(axis=0)
        std = np.where(matrix.std(axis=0) < 1e-6, 1.0, matrix.std(axis=0))
        z = np.abs((vector - mean) / std)
        raw = float(np.mean(z))
        score = max(0.0, min(raw / 4.0, 1.0))
        label = "anomalous" if score >= 0.65 else "normal"
        self.history.append(vector)
        self.history = self.history[-256:]
        return score, label


class IsolationForestDetector:
    def __init__(self) -> None:
        self.model = None
        self.fallback = RollingFallbackDetector()
        if IsolationForest is not None:
            baseline = np.vstack([vectorize(sample) for sample in self.fallback._seed_samples()])
            self.model = IsolationForest(
                n_estimators=64,
                contamination=0.1,
                random_state=7,
            )
            self.model.fit(baseline)

    @property
    def model_name(self) -> str:
        return "IsolationForest" if self.model is not None else "RollingZScoreFallback"

    def analyze(self, features: Dict[str, float]) -> Dict[str, Any]:
        vector = vectorize(features).reshape(1, -1)
        if self.model is None:
            score, label = self.fallback.score(vector[0])
            return {"score": score, "label": label}

        raw_score = float(-self.model.score_samples(vector)[0])
        score = max(0.0, min(raw_score / 0.8, 1.0))
        label = "anomalous" if self.model.predict(vector)[0] == -1 else "normal"
        return {"score": score, "label": label}


MODEL = IsolationForestDetector()
APP_STARTED_AT = time.time()
app = FastAPI(title="EmION ML Detector")


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "uptime_s": round(time.time() - APP_STARTED_AT, 3)}


@app.get("/info")
async def info() -> Dict[str, Any]:
    return {
        "name": "Bundle Feature Detector",
        "description": "Unsupervised anomaly detector over bundle-level timing and routing features.",
        "model": MODEL.model_name,
        "features": FEATURE_ORDER,
    }


@app.post("/train")
async def train(data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    samples = data.get("data") or []
    if IsolationForest is None:
        return {"status": "skipped", "reason": "scikit-learn unavailable"}
    if not samples:
        return {"status": "ignored", "samples": 0}

    matrix = []
    for sample in samples:
        if isinstance(sample, dict):
            matrix.append(vectorize(sample))
    if not matrix:
        return {"status": "ignored", "samples": 0}

    model = IsolationForest(
        n_estimators=64,
        contamination=0.1,
        random_state=7,
    )
    model.fit(np.vstack(matrix))
    MODEL.model = model
    return {"status": "trained", "samples": len(matrix)}


@app.post("/analyze")
async def analyze(data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    started = time.perf_counter()
    metadata = data.get("metadata") or {}
    features = extract_features(metadata)
    result = MODEL.analyze(features)
    score = float(result["score"])
    latency_ms = (time.perf_counter() - started) * 1000.0
    return {
        "is_anomaly": score >= 0.65,
        "score": round(score, 6),
        "label": result["label"],
        "model": MODEL.model_name,
        "inference_latency_ms": round(latency_ms, 3),
        "details": {
            "feature_vector": {name: round(features[name], 6) for name in FEATURE_ORDER},
            "feature_norm": round(float(np.linalg.norm(vectorize(features))), 6),
        },
    }


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8421)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)

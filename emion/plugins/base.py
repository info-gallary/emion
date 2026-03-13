"""
EmionPlugin — Base class for API-based plugins.

Users implement their anomaly detection as a FastAPI app (api.py).
EmION calls the user's endpoints via HTTP during simulation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import json

try:
    import urllib.request
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False


class EmionPlugin(ABC):
    """
    Base class for EmION plugins.
    Subclass this or provide a FastAPI-based api.py.
    """

    name: str = "BasePlugin"
    version: str = "0.0.0"

    @abstractmethod
    def process(self, payload: bytes) -> Dict[str, Any]:
        """Process a bundle payload and return analysis results."""
        ...


class APIPlugin:
    """
    Connects to a user-provided FastAPI endpoint for anomaly detection.

    The user provides an api.py with endpoints like:
        POST /analyze   — receives payload, returns anomaly result
        GET  /health    — returns plugin health/status
        GET  /info      — returns plugin metadata

    EmION calls these during simulation for each bundle.
    """

    def __init__(self, base_url: str = "http://localhost:8421", name: str = "UserPlugin"):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self._connected = False

    def health_check(self) -> bool:
        """Check if the user's API is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                self._connected = data.get("status") == "ok"
                return self._connected
        except Exception:
            self._connected = False
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get plugin info from the user's API."""
        try:
            req = urllib.request.Request(f"{self.base_url}/info")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}

    def analyze(self, payload: bytes, metadata: dict = None) -> Dict[str, Any]:
        """
        Send a bundle payload to the user's /analyze endpoint.

        Expected response format:
        {
            "is_anomaly": bool,
            "score": float,       # 0.0 = normal, 1.0 = extreme anomaly
            "label": str,         # e.g. "normal", "drift", "attack"
            "details": {...}      # any extra info
        }
        """
        try:
            body = json.dumps({
                "payload": payload.decode("utf-8", errors="replace"),
                "payload_hex": payload.hex(),
                "size": len(payload),
                "metadata": metadata or {},
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/analyze",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"is_anomaly": False, "score": 0.0, "error": str(e)}

    def train(self, data_batch: list, labels: list = None) -> Dict[str, Any]:
        """
        Send training data to the user's /train endpoint (optional).
        """
        try:
            body = json.dumps({
                "data": [d.hex() if isinstance(d, bytes) else d for d in data_batch],
                "labels": labels,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/train",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}

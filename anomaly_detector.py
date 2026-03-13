"""
Sample Anomaly Detection Module for EmION.
This tracks bundle payloads and flags "MALICIOUS" strings as anomalies.
"""

from fastapi import FastAPI, Body
from typing import Dict, Any

app = FastAPI(title="EmION Sample Anomaly Detector")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "anomaly_detector"}

@app.get("/info")
async def info():
    return {
        "name": "Heuristic Detector v1",
        "description": "Checks for suspicious strings in bundle payloads.",
        "author": "EmION Team"
    }

@app.post("/analyze")
async def analyze(data: Dict[str, Any] = Body(...)):
    """
    Called by EmION dashboard for each bundle.
    data format: { "payload": str, "metadata": { "src": str, "dst": str, ... } }
    """
    payload = data.get("payload", "")
    metadata = data.get("metadata", {})
    
    # Simple heuristic: look for 'MALICIOUS' keyword
    is_anomaly = "MALICIOUS" in payload.upper()
    score = 0.95 if is_anomaly else 0.05
    
    return {
        "is_anomaly": is_anomaly,
        "score": score,
        "label": "attack" if is_anomaly else "normal",
        "details": {
            "source": metadata.get("src"),
            "target": metadata.get("dst"),
            "reason": "Suspicious keyword detected" if is_anomaly else "Payload looks safe"
        }
    }

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8421)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)

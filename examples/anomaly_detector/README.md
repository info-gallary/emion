# Anomaly Detector Example

A sample **FastAPI-based ML inference module** that can be attached to any EmION node.

## Usage

```bash
pip install fastapi uvicorn
python anomaly_detector.py
```

Then in the EmION dashboard:
1. Open **ML MODULES** in the sidebar
2. Select a target node
3. Set URL to `http://localhost:8421`
4. Click **⧫ Attach to Node**

The node will auto-feed telemetry and bundle data to this module every 3 seconds.

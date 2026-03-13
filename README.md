# ⚛️ EmION — Professional ION-DTN Simulation

EmION is an authentic, production-ready Delay-Tolerant Networking (DTN) simulation framework. Unlike other simulators, EmION uses the **real ION-DTN C-engine** and **Contact Graph Routing (CGR)** for 100% protocol authenticity.

---

## 🚀 1. Installation

EmION requires **ION-DTN** (C-engine) and **pyion** to be installed on your Linux system.

### One-Click Setup
We provide a unified installer that checks dependencies and installs the package:
```bash
chmod +x install.sh
./install.sh
```

### Manual Installation
```bash
pip install -e ".[dashboard]"
```

---

## 🧪 2. Verification

Ensure your environment is correctly configured by running the professional test suite. This verifies real-time bundle transit and CGR routing:
```bash
python3 tests/test_emion.py
```

---

## 🛰️ 3. Usage

### Launching Mission Control
Start the visual dashboard to manage multi-node topologies and view live telemetry:
```bash
emion dashboard
```
- **URL**: `http://localhost:8420`
- **Telemetry**: Real-time SDR memory and bundle tracking.
- **Visuals**: Canvas-based topology with bundle animation.

### Command Line Interface
```bash
emion info      # Check ION system status
emion dashboard # Start visual UI
```

---

## 🔌 4. Connecting Third-Party Modules (API)

EmION supports selective attachment of Anomaly Detection or Security modules via a **FastAPI-based Plugin System**.

### Step A: Implement your Plugin
Your module must be a web service (FastAPI) with these endpoints:
1. `GET /health` -> `{"status": "ok"}`
2. `POST /analyze` -> Receives bundle `payload` and `metadata`, returns:
   ```json
   {
     "is_anomaly": true,
     "score": 0.95,
     "label": "attack",
     "details": {"reason": "Payload too large"}
   }
   ```

### Step B: Connect to EmION
In the Dashboard UI (or via API), connect your module:
- **Module URL**: `http://localhost:8421`
- **Target Nodes**: Selectively monitor specific nodes (e.g., `1,3`) or `all`.

### Demo Reference
See `anomaly_detector.py` for a functional sample implementation.

---

## 🐳 5. Docker (Self-Contained BPv7)

Run the entire EmION environment (ION-DTN + pyion + Dashboard) without local installation.

### Build and Run
```bash
docker build -t emion .
docker run -p 8420:8420 emion
```
Access Mission Control at `http://localhost:8420`.

---

## 📦 6. Publishing to PyPI

### Build the Package
```bash
pip install build twine
python3 -m build
```

### Upload to PyPI
```bash
twine upload dist/*
```

---

## 🏗️ Project Structure
- `emion/` — Core BPv7 orchestration.
- `docs/` — [Coding Guide](docs/coding_guide.md) & [Usage Notebook](docs/usage_demo.ipynb).
- `ION-DTN/` — Authentic NASA-JPL C-Engine.
- `Dockerfile` — Professional self-contained environment.
- `README.md` — This guide.

---

**Authentic. Professional. Space-Ready.** ⚛️
- ION-DTN (compiled, with ionadmin/bpadmin in PATH)
- pyion (built against your ION installation)
- FastAPI + uvicorn + websockets (for dashboard)

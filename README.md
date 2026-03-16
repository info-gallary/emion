# ⚛️ EmION — Professional ION-DTN Simulation

EmION is an authentic, production-ready Delay-Tolerant Networking (DTN) simulation framework. Unlike other simulators, EmION uses the **real ION-DTN C-engine** and **Contact Graph Routing (CGR)** for 100% protocol authenticity.

---

## 🌍 1. Platform Compatibility

EmION relies on the **NASA-JPL ION-DTN** C-engine. Choose your platform:

| Platform | Support | Recommendation |
| :--- | :--- | :--- |
| **Linux (Ubuntu/Debian)** | ✅ Native | **Recommended**. Use the `install.sh` for one-click setup. |
| **Windows (WSL2)** | ✅ Supported | **Best for Windows**. Install Ubuntu 22.04 on WSL2 and follow Linux steps. |
| **Docker (Any OS)** | ✅ Containerized | **Easiest**. Run the pre-built environment with zero local setup. |
| **Windows (Native)** | ❌ Not Supported | Use **WSL2** or **Docker**. ION-DTN requires a POSIX environment. |

---

## 🚀 2. Installation

### Quick Start (PyPI)
Install the framework and dashboard directly from PyPI:
```bash
pip install "emion[dashboard]"
```

### One-Click Installer (Linux/WSL)
For a complete environment setup (including building ION-DTN and pyion from source):
```bash
git clone https://github.com/info-gallary/emion.git
cd emion
chmod +x install.sh
./install.sh
```

---

## 🧪 3. Verification

Ensure your environment is correctly configured by running the professional test suite. This verifies real-time bundle transit and CGR routing:
```bash
python3 tests/test_emion.py
```

---

## 🛰️ 4. Usage

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

## 🔌 5. Connecting Third-Party Modules (API)

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

### 🐳 One-Command Deployment (Docker)

If you have Docker installed, you don't need to clone, install, or compile anything locally. The Docker image is **self-contained**, meaning it includes the NASA ION-DTN engine, all Python bindings, and the Mission Control Dashboard out-of-the-box.

```bash
# 1. Build the professional image (one-time setup)
docker build -t emion .

# 2. Launch the entire mission control
docker run -p 8420:8420 emion
```

**Pre-built Image (Zero-Cloning Workflow):**
If you choose to push your image to a registry (like Docker Hub), then anyone can run it with just one command:
`docker run -p 8420:8420 your-username/emion`
This is the ultimate way to share your work—literally no setup required for the user.
Access Mission Control at `http://localhost:8420`.

---

## 📦 7. Package Management (Developers)

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

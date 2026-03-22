# ⚛️ EmION — Research-Grade ION-DTN Simulation

> **Built with 💻 by Team DOMinators**

**EmION** is an authentic, research-grade Delay-Tolerant Networking (DTN) simulation framework. Unlike other simulators, EmION uses the **real NASA-JPL ION-DTN C-engine** and **Contact Graph Routing (CGR)** for 100% protocol authenticity — with a state-of-the-art visual dashboard and per-node ML module attachment.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org)

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Real ION-DTN** | Uses the actual NASA-JPL ION C-engine — not a simulator |
| **BPv7 + CGR** | Full Bundle Protocol v7 with Contact Graph Routing |
| **WLAN Mobility** | Spatial distance-based wireless link management |
| **XML Scenario Import** | Load CORE GUI `.xml` scenarios directly |
| **Scenario Briefing** | Plain-English mission summary from any loaded scenario |
| **Per-Node ML Modules** | Attach anomaly detectors, BPSec signers to specific nodes |
| **Auto-Feed Pipeline** | Nodes automatically stream telemetry to attached modules |
| **Visual Dashboard** | Real-time canvas with node LEDs, bundle animation, HUD overlays |
| **CFDP Support** | Authentic file delivery over DTN |

---

## 🌍 Platform Support

| Platform | Support | Notes |
|----------|---------|-------|
| **Linux (Ubuntu/Debian)** | ✅ Native | Recommended. Use `install.sh` |
| **Windows (WSL2)** | ✅ Supported | Ubuntu 22.04 on WSL2 |
| **Docker** | ✅ Containerized | Zero local setup |
| **Windows (Native)** | ❌ | Use WSL2 or Docker |

---

## 🚀 Installation

### From PyPI
```bash
pip install "emion[dashboard]"
```

### From Source
```bash
git clone https://github.com/info-gallary/emion.git
cd emion
pip install -e ".[dashboard]"
```

### Full Environment (Linux/WSL)
```bash
chmod +x install.sh && ./install.sh
```

---

## 🛰️ Usage

### Launch the Dashboard
```bash
emion dashboard
```
Open **http://localhost:8420** in your browser.

### CLI
```bash
emion info       # ION system status
emion dashboard  # Start the visual dashboard
```

---

## 🧪 XML Scenario Import

Upload any CORE `.xml` scenario directly in the dashboard:

1. Open **Scenario Engine** in the sidebar
2. Drag-and-drop your `.xml` file (or click **Browse Files**)
3. A **Scenario Briefing** appears in the telemetry panel with a plain-English summary
4. Click **▶ Start** to begin the simulation

See [`examples/ion_mars/`](examples/ion_mars/) for a sample scenario.

---

## 🔌 Per-Node ML Modules

Attach ML inference modules (anomaly detectors, security analyzers) to **specific nodes**. The node automatically feeds all telemetry and bundle data to the attached module.

### Quick Start
1. Start your module (a FastAPI server with `/health` and `/analyze` endpoints)
2. In the dashboard sidebar → **ML MODULES**
3. Select a node → pick module type → enter the API URL → **Attach**
4. Watch the canvas LED indicators (🟢/🟡/🔴) change in real-time

### Module API Contract
Your module must expose:
- `GET /health` → `{"status": "ok"}`
- `POST /analyze` → receives `{"payload": ..., "metadata": {...}}`, returns `{"is_anomaly": bool, "score": float}`

See [`examples/anomaly_detector/`](examples/anomaly_detector/) for a reference implementation.

---

## 🐳 Docker

```bash
docker build -t emion .
docker run -p 8420:8420 emion
```

---

## 📦 Project Structure

```
emion/
├── emion/                  # Core Python package (BPv7, CGR, Dashboard)
│   ├── core/               # ION engine, scenarios, WLAN mobility
│   ├── dashboard/          # FastAPI server + static UI
│   ├── plugins/            # Module base classes (APIPlugin)
│   └── pyion/              # C-extension bindings for ION
├── examples/               # User-facing research examples
│   ├── ion_mars/           # CORE XML scenario (5 WLAN nodes)
│   ├── anomaly_detector/   # Sample ML inference module
│   └── core_services/      # CORE integration scripts
├── scripts/                # Maintenance & developer utilities
├── docs/                   # Coding guide & usage notebook
├── tests/                  # Test suite
├── Dockerfile              # Self-contained build
├── pyproject.toml          # Package config (v0.4)
├── LICENSE                 # MIT
└── CONTRIBUTING.md         # How to contribute
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📜 License

MIT License — see [LICENSE](LICENSE).

---

**Authentic. Professional. Space-Ready.** ⚛️

Built by **Team DOMinators** using the real NASA-JPL ION-DTN engine.


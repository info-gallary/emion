# ⚛️ EmION: Comprehensive Coding & Integration Guide

Welcome to the EmION technical guide. This document provides a deep dive into programmatically orchestrating authentic BPv7 networks using the EmION framework.

---

## 🏗️ 1. Architectural Overview

EmION is built on three layers:
1.  **C-Engine Layer**: Authentic NASA-JPL ION-DTN 4.x binaries.
2.  **Binding Layer**: `pyion` C-extensions for zero-copy memory access.
3.  **Orchestration Layer**: EmION's Python API for high-level management.

---

## 🛠️ 2. Core Orchestration API

The `emion.core.network` module is the primary entry point for research scripts.

### Basic Setup
```python
from emion.core import network

# 1. Define and Register Nodes
nodes = [1, 2, 3]
for nid in nodes:
    network.register_node(nid)

# 2. Boot ION Core
# This handles the complex ionadmin/bpadmin/ipnadmin bootstrapping
network.start_core(cleanup=True)
```

### Dispatching Bundles (BPv7)
Bundles are dispatched using real IPN endpoints (`ipn:node.service`).
```python
# Send from Node 1 to Node 3
result = network.send_bundle(
    src=1, 
    dst=3, 
    payload="MISSION_DATA_V7"
)

print(f"Bundle {result['bundle_id']} currently in transit.")
```

---

## 🔌 3. Plug-in Architecture (Security & Anomaly)

EmION allows you to "hook" into the bundle flow via external APIs.

### Implementing a Plugin (FastAPI)
```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "name": "DeepShield-V7"}

@app.post("/analyze")
async def analyze(request: Request):
    data = await request.json()
    payload = data.get("payload")
    metadata = data.get("metadata")
    
    # Custom logic: Flag payloads over 100 bytes
    is_anomaly = len(payload) > 100
    
    return {
        "is_anomaly": is_anomaly,
        "score": 0.99 if is_anomaly else 0.01,
        "details": {"size": len(payload)}
    }
```

### Attaching the Plugin
```python
network.attach_plugin("http://localhost:8421", target_nodes="all")
```

---

## 🧪 4. Testing & Verification

For production research, always use the unified test suite to verify routing integrity.
```bash
python3 tests/test_emion.py
```

---

## 📝 5. Best Practices
- **Cleanup**: Always call `network.stop_core()` or use the `killm` command if a script crashes to release shared memory.
- **Stabilization**: ION requires ~5 seconds to propagate Contact Graph updates after boot.
- **BPv7**: Ensure your `pyion` is built with `--enable-bpv7` for full protocol authenticity.

---
**EmION Team** · *Authentic Space Research Framework*

"""
EmION Dashboard — FastAPI backend for real-time ION-DTN visual simulation.
Minimum 2 nodes required. All operations use real ION C-engine + pyion.
Optional user-provided anomaly/security API modules can be connected.
"""

import json
import time
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from emion.core.node import EmionNode
from emion.core.engine import EmionEngine
from emion.plugins.base import APIPlugin


# ── State ─────────────────────────────────────────────────────
nodes: Dict[int, EmionNode] = {}
engines: Dict[int, EmionEngine] = {}
user_modules: Dict[str, APIPlugin] = {}   # optional user-provided APIs
event_log: List[dict] = []
ws_clients: List[WebSocket] = []


def create_app() -> "FastAPI":
    if not FASTAPI_AVAILABLE:
        raise ImportError("pip install fastapi uvicorn websockets")

    app = FastAPI(title="EmION Dashboard", version="0.1.0",
                  description="Real-time ION-DTN Visual Simulation")
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static)), name="static")

    # ── UI ────────────────────────────────────────────────────

    @app.get("/")
    async def index():
        return FileResponse(str(static / "index.html"))

    # ── Nodes (real ION-DTN) ──────────────────────────────────

    @app.post("/api/nodes")
    async def create_node(node_id: int):
        """Boot an authentic ION-DTN node."""
        if node_id in nodes:
            return {"error": f"Node {node_id} exists"}
        n = EmionNode(node_id)
        # auto-register routing to all existing nodes (and vice-versa)
        for eid, existing in nodes.items():
            n.connect_to(eid)
            existing.connect_to(node_id)
        nodes[node_id] = n
        return {"status": "created", "node_id": node_id, "note": "Call POST /api/start to boot all"}

    @app.post("/api/start")
    async def start_all():
        """Boot all registered nodes and attach engines. Min 2 nodes required."""
        if len(nodes) < 2:
            return {"error": "Minimum 2 nodes required. Add more via POST /api/nodes"}
        # Global cleanup first
        subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        results = []
        for nid, n in nodes.items():
            try:
                n.start(cleanup=False)
                results.append({"node": nid, "status": "booted"})
            except Exception as e:
                results.append({"node": nid, "status": "error", "msg": str(e)})
        # Wait for stabilisation
        time.sleep(6)
        # Attach engines
        for nid in nodes:
            try:
                eng = EmionEngine(nid)
                eng.attach()
                engines[nid] = eng
                results.append({"node": nid, "status": "engine_attached"})
            except Exception as e:
                err_msg = str(e)
                results.append({"node": nid, "status": "attach_error", "msg": err_msg})
                # Broadcast error to UI
                await broadcast({"type": "network_error", "node": nid, "msg": f"Engine Attach Failed: {err_msg}"})
        await broadcast({"type": "network_started", "nodes": list(nodes.keys())})
        return {"status": "started", "details": results}

    @app.post("/api/stop")
    async def stop_all():
        """Shut down all ION nodes."""
        for n in nodes.values():
            try:
                n.stop()
            except Exception:
                pass
        engines.clear()
        subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await broadcast({"type": "network_stopped"})
        return {"status": "stopped"}

    @app.get("/api/nodes")
    async def list_nodes():
        return [n.status() for n in nodes.values()]

    # ── Links (auto-managed via connect_to) ───────────────────

    @app.get("/api/links")
    async def list_links():
        links = []
        seen = set()
        for nid, n in nodes.items():
            for pid in n._peers:
                key = tuple(sorted([nid, pid]))
                if key not in seen:
                    seen.add(key)
                    links.append({"from": key[0], "to": key[1]})
        return links

    # ── Bundles (real ION BP) ─────────────────────────────────

    @app.post("/api/send")
    async def send_bundle(from_node: int, to_node: int, payload: str = "EMION_TEST"):
        """Send a real BP bundle between ION nodes."""
        if from_node not in engines:
            return {"error": f"No engine for node {from_node}"}
        src = f"ipn:{from_node}.1"
        dst = f"ipn:{to_node}.1"
        data = payload.encode()
        try:
            engines[from_node].send(src, dst, data)
        except Exception as e:
            return {"error": str(e)}

        # Call optional user modules (Selective Support)
        module_results = {}
        for name, mod in user_modules.items():
            targets = getattr(mod, "target_nodes", "all")
            if targets == "all" or str(from_node) in targets or str(to_node) in targets:
                module_results[name] = mod.analyze(data, {"src": src, "dst": dst, "from_node": from_node, "to_node": to_node})

        evt = {"type": "bundle_sent", "from": from_node, "to": to_node,
               "src": src, "dst": dst, "size": len(data), "ts": time.time(),
               "modules": module_results}
        event_log.append(evt)
        await broadcast(evt)
        return evt

    # ... receive_bundle ...

    # ── Optional User Modules (anomaly, security, etc.) ───────

    @app.post("/api/modules/connect")
    async def connect_module(url: str, name: str = "", target_nodes: str = "all"):
        """Connect an optional user-provided API module. target_nodes='1,2,3' or 'all'."""
        mod = APIPlugin(base_url=url, name=name or url)
        if mod.health_check():
            info = mod.get_info()
            mod.name = info.get("name", name or url)
            mod.target_nodes = target_nodes.split(",") if target_nodes != "all" else "all"
            user_modules[mod.name] = mod
            await broadcast({"type": "module_connected", "name": mod.name, "url": url, "targets": target_nodes})
            return {"status": "ok", "name": mod.name, "info": info}
        return {"error": f"Cannot reach {url}/health"}

    @app.delete("/api/modules/{name}")
    async def disconnect_module(name: str):
        user_modules.pop(name, None)
        return {"status": "ok"}

    @app.get("/api/modules")
    async def list_modules():
        return [{"name": n, "url": m.base_url, "connected": m._connected}
                for n, m in user_modules.items()]

    # ── Events / WebSocket ────────────────────────────────────

    @app.get("/api/events")
    async def get_events(limit: int = 100):
        return event_log[-limit:]

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.append(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_clients.remove(ws)

    return app


async def telemetry_loop():
    """Background task to broadcast live telemetry to all clients."""
    while True:
        await asyncio.sleep(3)
        if not ws_clients:
            continue
            
        telemetry_data = []
        for nid, n in nodes.items():
            if n.is_running:
                telemetry_data.append(n.get_system_telemetry())
        
        if telemetry_data:
            await broadcast({"type": "telemetry_update", "data": telemetry_data})


async def broadcast(data: dict):
    msg = json.dumps(data, default=str)
    for ws in ws_clients[:]:
        try:
            await ws.send_text(msg)
        except Exception:
            ws_clients.remove(ws)


def run(host="0.0.0.0", port=8420):
    if not FASTAPI_AVAILABLE:
        print("[EmION] pip install fastapi uvicorn websockets")
        return
    app = create_app()
    
    # Start telemetry loop
    @app.on_event("startup")
    async def startup_event():
        asyncio.create_task(telemetry_loop())

    print(f"\n  ⚛  EmION Dashboard — Authentic ION-DTN")
    print(f"     http://localhost:{port}")
    print(f"     API docs: http://localhost:{port}/docs\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")

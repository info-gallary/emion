"""
EmION Dashboard — FastAPI backend for real-time ION-DTN visual simulation.
Minimum 2 nodes required. All operations use real ION C-engine + pyion.
Optional user-provided anomaly/security API modules can be connected.
"""

import json
import time
import asyncio
import subprocess
import os
from pathlib import Path
from typing import Dict, List

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from emion.core.node import EmionNode
from emion.core.engine import EmionEngine
from emion.core.scenarios import ScenarioManager
from emion.core.mars_import import build_ion_mars_scenario
from emion.plugins.base import APIPlugin


# ── State ─────────────────────────────────────────────────────
nodes: Dict[int, EmionNode] = {}
engines: Dict[int, EmionEngine] = {}
node_modules: Dict[int, List[APIPlugin]] = {}   # per-node ML modules
node_module_status: Dict[int, Dict[str, dict]] = {}  # per-node module last results
event_log: List[dict] = []
ws_clients: List[WebSocket] = []
scenario_mgr = ScenarioManager()
current_briefing: dict = {}  # cached scenario briefing


def generate_briefing(scenario: dict) -> dict:
    """Generate a plain-English briefing from a parsed scenario."""
    events = scenario.get("events", [])
    wlan_nodes = scenario.get("wlan_nodes", [])
    wlan_range = scenario.get("wlan_range", 200.0)
    name = scenario.get("name", "Unknown")

    # Collect unique node IDs from all events
    all_nodes = set()
    action_counts = {}
    movements = []
    max_time = 0
    for e in events:
        action = e.get("action", "")
        args = e.get("args", [])
        t = e.get("time", 0)
        max_time = max(max_time, t)
        action_counts[action] = action_counts.get(action, 0) + 1
        if action in ("add_contact", "delete_contact"):
            offset = 1 if len(args) >= 8 or (action == "delete_contact" and len(args) >= 5) else 0
            if len(args) > offset + 1:
                all_nodes.add(args[offset])
                all_nodes.add(args[offset + 1])
        elif action in ("add_range", "delete_range"):
            if len(args) >= 2:
                all_nodes.add(args[0])
                all_nodes.add(args[1])
        elif action == "set_position":
            if args: all_nodes.add(args[0])
        elif action == "move_linear":
            if args:
                all_nodes.add(args[0])
                movements.append({
                    "node": args[0],
                    "from": f"({args[1]:.0f}, {args[2]:.0f})" if len(args) >= 3 else "?",
                    "to": f"({args[3]:.0f}, {args[4]:.0f})" if len(args) >= 5 else "?",
                    "duration": f"{args[5]:.0f}s" if len(args) >= 6 else "?"
                })
    for n in wlan_nodes:
        all_nodes.add(n)

    sorted_nodes = sorted(all_nodes)
    node_labels = ", ".join(f"N{n}" for n in sorted_nodes)
    wired_count = len(sorted_nodes) - len(wlan_nodes)

    # Build summary lines
    lines = [f"{len(sorted_nodes)} Nodes ({node_labels})"]
    if wlan_nodes:
        wlan_labels = ", ".join(f"N{n}" for n in sorted(wlan_nodes))
        lines.append(f"{len(wlan_nodes)} WLAN wireless ({wlan_labels}, range: {wlan_range}m)")
    if wired_count > 0:
        lines.append(f"{wired_count} with scheduled wired links")
    lines.append(f"{len(events)} events over ~{max_time:.0f} seconds")
    for action, count in sorted(action_counts.items()):
        label = action.replace("_", " ")
        lines.append(f"  • {count}× {label}")
    if movements:
        for m in movements[:5]:
            lines.append(f"  ↗ N{m['node']} moves {m['from']} → {m['to']} ({m['duration']})")
        if len(movements) > 5:
            lines.append(f"  ... and {len(movements) - 5} more movements")

    return {
        "name": name,
        "node_count": len(sorted_nodes),
        "node_ids": sorted_nodes,
        "wlan_count": len(wlan_nodes),
        "wlan_range": wlan_range,
        "event_count": len(events),
        "duration": max_time,
        "action_counts": action_counts,
        "movement_count": len(movements),
        "summary_lines": lines
    }


def create_app() -> "FastAPI":
    if not FASTAPI_AVAILABLE:
        raise ImportError("pip install fastapi uvicorn websockets")

    app = FastAPI(title="EmION Dashboard", version="0.3.0",
                  description="Real-time ION-DTN Visual Simulation")
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static)), name="static")

    # ── UI ────────────────────────────────────────────────────

    @app.get("/")
    async def index():
        return FileResponse(str(static / "index.html"))

    # ── Scenarios (Complete Potential) ───────────────────────

    EMION_BASE_DIR = os.path.expanduser("~/ion_mars")
    scenario_dir = Path(EMION_BASE_DIR) / "scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    
    repo_root = Path(__file__).resolve().parents[2]
    mars_xml_path = repo_root / "ion_mars" / "mars.xml"
    if mars_xml_path.exists():
        ion_mars_scenario = build_ion_mars_scenario(mars_xml_path)
        (scenario_dir / "ion_mars_original.json").write_text(
            json.dumps(ion_mars_scenario, indent=2)
        )
        
    if not (scenario_dir / "mars_rover_mobility.json").exists():
        (scenario_dir / "mars_rover_mobility.json").write_text(json.dumps({
            "name": "Mars Rover Mobility (3 Nodes, 25s)",
            "events": [
                {"time": 2, "action": "add_contact", "args": [1, 3, "+0", "+3600", 1000000, 1.0, 1]},
                {"time": 2, "action": "add_contact", "args": [3, 1, "+0", "+3600", 1000000, 1.0, 1]},
                {"time": 2, "action": "add_range", "args": [1, 3, "+0", "+3600", 2, 1]},
                {"time": 2, "action": "add_range", "args": [3, 1, "+0", "+3600", 2, 1]},

                {"time": 10, "action": "add_range", "args": [1, 3, "+0", "+3600", 8, 1]},
                {"time": 10, "action": "add_range", "args": [3, 1, "+0", "+3600", 8, 1]},

                {"time": 15, "action": "delete_contact", "args": [1, 3, "+0", 1]},
                {"time": 15, "action": "delete_contact", "args": [3, 1, "+0", 1]},

                {"time": 20, "action": "add_contact", "args": [2, 3, "+0", "+3600", 1000000, 1.0, 1]},
                {"time": 20, "action": "add_contact", "args": [3, 2, "+0", "+3600", 1000000, 1.0, 1]},
                {"time": 20, "action": "add_range", "args": [2, 3, "+0", "+3600", 3, 1]},
                {"time": 20, "action": "add_range", "args": [3, 2, "+0", "+3600", 3, 1]}
            ]
        }, indent=2))

    if not (scenario_dir / "satellite_orbit.json").exists():
        (scenario_dir / "satellite_orbit.json").write_text(json.dumps({
            "name": "Satellite Orbit Pass (20s)",
            "events": [
                {"time": 2, "action": "add_contact", "args": [1, 1, 2, "+0", "+3600", 1000000, 1.0, 1]},
                {"time": 10, "action": "delete_contact", "args": [1, 1, 2, "+0", 1]},
                {"time": 20, "action": "add_contact", "args": [1, 1, 2, "+0", "+3600", 1000000, 1.0, 1]}
            ]
        }, indent=2))
        
    if not (scenario_dir / "lossy_intermittent.json").exists():
        (scenario_dir / "lossy_intermittent.json").write_text(json.dumps({
            "name": "Lossy / Intermittent (30s)",
            "events": [
                {"time": 5, "action": "add_range", "args": [1, 2, "+0", "+3600", 10, 1]},
                {"time": 15, "action": "delete_contact", "args": [1, 1, 2, "+0", 1]}
            ]
        }, indent=2))

    @app.get("/api/scenario/list")
    async def list_scenarios():
        scenarios = []
        for f in scenario_dir.glob("*.json"):
            try:
                meta = json.loads(f.read_text())
                briefing = generate_briefing(meta)
                scenarios.append({
                    "id": f.stem,
                    "name": meta.get("name", f.name),
                    "wlan_nodes": meta.get("wlan_nodes", []),
                    "wlan_range": meta.get("wlan_range", 200.0),
                    "events": meta.get("events", meta) if isinstance(meta, dict) else meta,
                    "briefing": briefing
                })
            except Exception:
                pass
        return scenarios

    @app.post("/api/scenario/load")
    async def load_scenario(scenario: dict):
        global current_briefing
        scenario_mgr.load_scenario(scenario)
        current_briefing = generate_briefing(scenario)
        events_len = len(scenario.get("events", []))
        await broadcast({"type": "scenario_loaded", "count": events_len, "briefing": current_briefing})
        return {"status": "loaded", "count": events_len, "briefing": current_briefing}

    @app.post("/api/scenario/start")
    async def start_scenario():
        scenario_mgr.set_nodes([n.node_dir for n in nodes.values()])
        scenario_mgr.start()
        await broadcast({"type": "scenario_started"})
        return {"status": "started"}

    @app.post("/api/scenario/stop")
    async def stop_scenario():
        scenario_mgr.stop()
        await broadcast({"type": "scenario_stopped"})
        return {"status": "stopped"}

    @app.get("/api/scenario/status")
    async def scenario_status():
        return scenario_mgr.get_status()

    @app.post("/api/scenario/upload-xml")
    async def upload_xml(file: UploadFile = File(...)):
        """Accept a .xml CORE scenario file and parse it."""
        content = await file.read()
        tmp = Path("/tmp") / file.filename
        tmp.write_bytes(content)
        try:
            scenario = build_ion_mars_scenario(tmp)
            out_name = tmp.stem
            (scenario_dir / f"{out_name}.json").write_text(json.dumps(scenario, indent=2))
            briefing = generate_briefing(scenario)
            return {"status": "parsed", "name": scenario["name"], "events": len(scenario["events"]), "briefing": briefing}
        except Exception as e:
            return {"error": str(e)}

    # ── Nodes (real ION-DTN) ──────────────────────────────────

    @app.post("/api/nodes")
    async def create_node(node_id: int):
        """Boot an authentic ION-DTN node."""
        if node_id in nodes:
            return {"error": f"Node {node_id} exists"}
        n = EmionNode(node_id, base_dir=EMION_BASE_DIR)
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
                eng = EmionEngine(nid, base_dir=EMION_BASE_DIR)
                eng.attach()
                engines[nid] = eng
                results.append({"node": nid, "status": "engine_attached"})
            except Exception as e:
                results.append({"node": nid, "status": "attach_error", "msg": str(e)})
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
        if scenario_mgr.is_running:
            return scenario_mgr.get_active_links()
            
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

        # Auto-feed to per-node modules — both source and destination modules
        module_results = {}
        bundle_meta = {"src": src, "dst": dst, "from_node": from_node, "to_node": to_node}
        for nid in [from_node, to_node]:
            for mod in node_modules.get(nid, []):
                try:
                    result = mod.analyze(data, bundle_meta)
                    key = f"N{nid}:{mod.name}"
                    module_results[key] = result
                    node_module_status.setdefault(nid, {})[mod.name] = result
                except Exception as e:
                    module_results[f"N{nid}:{mod.name}"] = {"error": str(e)}

        evt = {"type": "bundle_sent", "from": from_node, "to": to_node,
               "src": src, "dst": dst, "size": len(data), "ts": time.time(),
               "modules": module_results}
        event_log.append(evt)
        await broadcast(evt)
        return evt

    # ── CFDP (File Delivery) ──────────────────

    @app.post("/api/cfdp/send")
    async def cfdp_send(from_node: int, to_node: int, file: str):
        """Initiate an authentic CFDP file transfer."""
        if from_node not in engines:
            return {"error": f"No engine for node {from_node}"}
        try:
            engines[from_node].send_file(to_node, file)
            return {"status": "cfdp_initiated", "file": file}
        except Exception as e:
            return {"error": str(e)}

    # ... receive_bundle ...

    # ── Per-Node Module Management ─────────────────────────────

    @app.post("/api/nodes/{node_id}/modules")
    async def attach_module(node_id: int, url: str, name: str = "", module_type: str = "anomaly"):
        """Attach an ML inference module to a specific node. The node auto-feeds telemetry."""
        mod = APIPlugin(base_url=url, name=name or f"{module_type}@N{node_id}")
        if mod.health_check():
            info = mod.get_info()
            mod.name = info.get("name", name or f"{module_type}@N{node_id}")
            mod.module_type = module_type
            mod.node_id = node_id
            node_modules.setdefault(node_id, []).append(mod)
            await broadcast({"type": "module_attached", "node_id": node_id, "name": mod.name, "module_type": module_type})
            return {"status": "ok", "node_id": node_id, "name": mod.name, "info": info}
        return {"error": f"Cannot reach {url}/health"}

    @app.delete("/api/nodes/{node_id}/modules/{mod_name}")
    async def detach_module(node_id: int, mod_name: str):
        mods = node_modules.get(node_id, [])
        node_modules[node_id] = [m for m in mods if m.name != mod_name]
        node_module_status.get(node_id, {}).pop(mod_name, None)
        await broadcast({"type": "module_detached", "node_id": node_id, "name": mod_name})
        return {"status": "ok"}

    @app.get("/api/nodes/{node_id}/modules")
    async def list_node_modules(node_id: int):
        return [{"name": m.name, "url": m.base_url, "type": getattr(m, 'module_type', 'unknown'),
                 "connected": m._connected} for m in node_modules.get(node_id, [])]

    @app.get("/api/modules")
    async def list_all_modules():
        result = []
        for nid, mods in node_modules.items():
            for m in mods:
                result.append({"node_id": nid, "name": m.name, "url": m.base_url,
                               "type": getattr(m, 'module_type', 'unknown'), "connected": m._connected})
        return result

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
    """Background task to broadcast live telemetry and auto-feed modules."""
    while True:
        await asyncio.sleep(3)
        if not ws_clients:
            continue
            
        telemetry_data = []
        for nid, n in nodes.items():
            if n.is_running:
                telem = n.get_system_telemetry()
                telemetry_data.append(telem)
                # Auto-feed: send node telemetry to all attached modules
                for mod in node_modules.get(nid, []):
                    try:
                        result = mod.analyze(
                            json.dumps(telem).encode(),
                            {"source": "auto_feed", "node_id": nid, "type": "telemetry"}
                        )
                        node_module_status.setdefault(nid, {})[mod.name] = result
                    except Exception:
                        node_module_status.setdefault(nid, {})[mod.name] = {"error": "unreachable"}

        # Build module status summary for the frontend
        module_summary = {}
        for nid, statuses in node_module_status.items():
            module_summary[nid] = {}
            for mod_name, result in statuses.items():
                is_anomaly = result.get("is_anomaly", False) if isinstance(result, dict) else False
                score = result.get("score", 0.0) if isinstance(result, dict) else 0.0
                has_error = "error" in result if isinstance(result, dict) else False
                module_summary[nid][mod_name] = {
                    "status": "error" if has_error else ("anomaly" if is_anomaly else "normal"),
                    "score": score
                }

        if telemetry_data or scenario_mgr.is_running:
            await broadcast({
                "type": "telemetry_update", 
                "data": telemetry_data,
                "scenario": scenario_mgr.get_status(),
                "scenario_telemetry": scenario_mgr.get_telemetry(),
                "scenario_links": scenario_mgr.get_active_links(),
                "node_positions": scenario_mgr.node_positions,
                "module_status": module_summary,
                "briefing": current_briefing
            })


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
        loop = asyncio.get_running_loop()
        def on_log(msg, ts):
            evt = {"type": "log", "tag": "sys", "msg": f"[T+{ts:.1f}s] {msg}"}
            event_log.append(evt)
            if getattr(loop, "is_closed", lambda: True)() is False:
                asyncio.run_coroutine_threadsafe(broadcast(evt), loop)
        scenario_mgr.log_callback = on_log
        asyncio.create_task(telemetry_loop())

    print(f"\n  ⚛  EmION Dashboard — Authentic ION-DTN")
    print(f"     http://localhost:{port}")
    print(f"     API docs: http://localhost:{port}/docs\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
if __name__ == "__main__":
    run()

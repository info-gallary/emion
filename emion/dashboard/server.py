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
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

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
from emion.core.mars_import import parse_core_xml_scenario
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
bundle_registry: Dict[str, Dict[str, Any]] = {}
dashboard_metrics: Dict[str, Any] = {}


def reset_dashboard_metrics():
    dashboard_metrics.clear()
    dashboard_metrics.update({
        "bundle_sent_count": 0,
        "bundle_received_count": 0,
        "bundle_timeout_count": 0,
        "bundle_bytes_sent": 0,
        "bundle_bytes_received": 0,
        "delivery_latencies_ms": [],
        "module_inference_latencies_ms": [],
        "module_auto_feed_latencies_ms": [],
        "telemetry_message_count": 0,
        "telemetry_bytes": 0,
        "broadcast_counts": defaultdict(int),
        "route_hops": [],
        "last_bundle_ts_by_flow": {},
        "feature_samples": [],
    })


reset_dashboard_metrics()


def _summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "avg": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 3),
        "max": round(max(values), 3),
    }


def _parse_time_token(token: Any) -> Optional[float]:
    if isinstance(token, (int, float)):
        return float(token)
    if isinstance(token, str):
        token = token.strip()
        if token.startswith("+"):
            token = token[1:]
        try:
            return float(token)
        except ValueError:
            return None
    return None


def _extract_trace_id_and_payload(data: bytes) -> tuple[Optional[str], bytes]:
    prefix = b"__EMION_TRACE__"
    if not data.startswith(prefix):
        return None, data
    try:
        marker_end = data.index(b"\n")
    except ValueError:
        return None, data
    trace_id = data[len(prefix):marker_end].decode("utf-8", errors="replace").strip()
    return trace_id or None, data[marker_end + 1:]


def _estimate_contact_duration(route: List[int]) -> float:
    if len(route) < 2:
        return 0.0
    first_hop = tuple(route[:2])
    for event in scenario_mgr.events:
        if event.action != "add_contact":
            continue
        args = event.args
        if len(args) == 7:
            from_node, to_node, tstart, tend = args[:4]
        elif len(args) >= 8:
            from_node, to_node, tstart, tend = args[1:5]
        else:
            continue
        if (int(from_node), int(to_node)) != first_hop:
            continue
        start_value = _parse_time_token(tstart)
        end_value = _parse_time_token(tend)
        if start_value is None or end_value is None:
            return 0.0
        return max(end_value - start_value, 0.0)
    return 0.0


def extract_bundle_features(from_node: int, to_node: int, payload: bytes, route_forecast: Dict[str, Any], ttl_seconds: int, retransmission_count: int) -> Dict[str, Any]:
    now = time.time()
    flow_key = f"{from_node}->{to_node}"
    last_ts = dashboard_metrics["last_bundle_ts_by_flow"].get(flow_key)
    inter_arrival_ms = 0.0 if last_ts is None else (now - last_ts) * 1000.0
    dashboard_metrics["last_bundle_ts_by_flow"][flow_key] = now

    route = route_forecast.get("predicted_path", []) or route_forecast.get("current_path", []) or []
    hop_count = max(len(route) - 1, 0)
    queue_delay_ms = max(route_forecast.get("available_at", 0.0) - scenario_mgr.current_time_relative, 0.0) * 1000.0
    features = {
        "bundle_size": len(payload),
        "inter_arrival_time_ms": round(inter_arrival_ms, 3),
        "hop_count": hop_count,
        "ttl_seconds": int(ttl_seconds),
        "queue_delay_ms": round(queue_delay_ms, 3),
        "retransmission_count": int(retransmission_count),
        "contact_duration_s": round(_estimate_contact_duration(route), 3),
        "route_length": len(route),
    }
    dashboard_metrics["route_hops"].append(hop_count)
    dashboard_metrics["feature_samples"].append(features)
    if len(dashboard_metrics["feature_samples"]) > 256:
        dashboard_metrics["feature_samples"] = dashboard_metrics["feature_samples"][-256:]
    return features


def get_dashboard_metrics() -> Dict[str, Any]:
    avg_active_bundles = 0.0
    if bundle_registry:
        active = [record for record in bundle_registry.values() if record.get("status") == "sent"]
        avg_active_bundles = float(len(active))
    return {
        "bundles": {
            "sent": dashboard_metrics["bundle_sent_count"],
            "received": dashboard_metrics["bundle_received_count"],
            "timeouts": dashboard_metrics["bundle_timeout_count"],
            "delivery_ratio": round(
                dashboard_metrics["bundle_received_count"] / dashboard_metrics["bundle_sent_count"],
                4,
            ) if dashboard_metrics["bundle_sent_count"] else 0.0,
            "bytes_sent": dashboard_metrics["bundle_bytes_sent"],
            "bytes_received": dashboard_metrics["bundle_bytes_received"],
            "delivery_latency_ms": _summarize(dashboard_metrics["delivery_latencies_ms"]),
        },
        "modules": {
            "bundle_inference_latency_ms": _summarize(dashboard_metrics["module_inference_latencies_ms"]),
            "telemetry_inference_latency_ms": _summarize(dashboard_metrics["module_auto_feed_latencies_ms"]),
        },
        "dashboard": {
            "telemetry_message_count": dashboard_metrics["telemetry_message_count"],
            "telemetry_bytes": dashboard_metrics["telemetry_bytes"],
            "broadcast_counts": dict(dashboard_metrics["broadcast_counts"]),
        },
        "routing": {
            "avg_hops": _summarize(dashboard_metrics["route_hops"]),
            "control_plane": scenario_mgr.get_metrics(),
        },
        "resources": {
            "active_bundles": avg_active_bundles,
        },
        "feature_samples": list(dashboard_metrics["feature_samples"][-20:]),
    }


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


def _normalize_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        normalized = dict(result)
    else:
        normalized = {"value": result}
    normalized.setdefault("is_anomaly", False)
    normalized.setdefault("score", 0.0)
    return normalized


def _extract_route_override(result: Dict[str, Any], from_node: int) -> Optional[Dict[str, Any]]:
    candidate = None
    for key in ("future_path", "recommended_path", "route", "path"):
        if key in result:
            candidate = result[key]
            break

    path_nodes = None
    available_at = result.get("available_at")
    reason = result.get("reason") or result.get("label") or "module_override"

    if isinstance(candidate, list):
        path_nodes = [int(node) for node in candidate]
    elif isinstance(candidate, dict):
        raw_path = candidate.get("path") or candidate.get("nodes")
        if isinstance(raw_path, list):
            path_nodes = [int(node) for node in raw_path]
        available_at = candidate.get("available_at", available_at)
        reason = candidate.get("reason", reason)

    next_hop = result.get("next_hop")
    if path_nodes is None and next_hop is not None:
        path_nodes = [int(from_node), int(next_hop)]

    if not path_nodes:
        return None

    return {
        "predicted_path": path_nodes,
        "available_at": round(float(available_at or 0.0), 2),
        "reason": str(reason),
    }


def process_bundle_pipeline(from_node: int, to_node: int, payload: bytes, *, ttl_seconds: int = 300, retransmission_count: int = 0) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Process a bundle through attached node modules and compute route guidance."""
    src = f"ipn:{from_node}.1"
    dst = f"ipn:{to_node}.1"
    route_forecast = scenario_mgr.get_future_path(from_node, to_node)
    features = extract_bundle_features(from_node, to_node, payload, route_forecast, ttl_seconds, retransmission_count)
    base_metadata = {
        "src": src,
        "dst": dst,
        "from_node": from_node,
        "to_node": to_node,
        "payload_size": len(payload),
        "ttl_seconds": ttl_seconds,
        "retransmission_count": retransmission_count,
        "scenario_status": scenario_mgr.get_status(),
        "scenario_telemetry": scenario_mgr.get_telemetry(),
        "route_forecast": route_forecast,
        "bundle_features": features,
    }

    module_results: Dict[str, Dict[str, Any]] = {}
    selected_route = None
    selected_by = "scenario"

    for nid in [from_node, to_node]:
        for mod in node_modules.get(nid, []):
            t0 = time.perf_counter()
            result = _normalize_result(
                mod.analyze(
                    payload,
                    {
                        **base_metadata,
                        "processing_node": nid,
                        "module_name": mod.name,
                    },
                )
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            result.setdefault("inference_latency_ms", round(latency_ms, 3))
            dashboard_metrics["module_inference_latencies_ms"].append(latency_ms)
            key = f"N{nid}:{mod.name}"
            module_results[key] = result
            node_module_status.setdefault(nid, {})[mod.name] = result

            override = _extract_route_override(result, from_node)
            if override and selected_route is None:
                selected_route = override
                selected_by = key

    route_plan = {
        **route_forecast,
        "selected_path": (selected_route or route_forecast).get("predicted_path", []),
        "selected_by": selected_by,
        "processing_mode": "module" if selected_route else "scenario",
    }
    if selected_route:
        route_plan["module_override"] = selected_route
    return module_results, route_plan, features


def create_app() -> "FastAPI":
    if not FASTAPI_AVAILABLE:
        raise ImportError("pip install fastapi uvicorn websockets")

    app = FastAPI(title="EmION Dashboard", version="1.0.0",
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
    mars_xml_path = repo_root / "examples" / "ion_mars" / "mars.xml"
    if mars_xml_path.exists():
        ion_mars_scenario = parse_core_xml_scenario(mars_xml_path)
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
        payload = {
            "type": "scenario_loaded",
            "count": events_len,
            "briefing": current_briefing,
            "scenario_links": scenario_mgr.get_active_links(),
            "node_positions": scenario_mgr.node_positions,
            "scenario_telemetry": scenario_mgr.get_telemetry(),
        }
        await broadcast(payload)
        return {
            "status": "loaded",
            "count": events_len,
            "briefing": current_briefing,
            "scenario_links": scenario_mgr.get_active_links(),
            "node_positions": scenario_mgr.node_positions,
            "scenario_telemetry": scenario_mgr.get_telemetry(),
        }

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
        safe_name = Path(file.filename or "scenario.xml").name
        with NamedTemporaryFile(delete=False, suffix=Path(safe_name).suffix or ".xml") as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        try:
            scenario = parse_core_xml_scenario(tmp_path)
            out_name = Path(safe_name).stem or tmp_path.stem
            (scenario_dir / f"{out_name}.json").write_text(json.dumps(scenario, indent=2))
            briefing = generate_briefing(scenario)
            return {
                "status": "parsed", 
                "id": out_name, 
                "name": scenario["name"], 
                "events": len(scenario["events"]), 
                "node_count": len([e for e in scenario["events"] if e["action"] == "set_position"]),
                "link_count": len([e for e in scenario["events"] if e["action"] == "add_contact"]) // 2,
                "wlan_node_count": len(scenario.get("wlan_nodes", [])),
                "briefing": briefing, 
                "scenario": scenario
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

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
    async def start_all(startup_wait: float = 6.0):
        """Boot all registered nodes and attach engines. Min 2 nodes required."""
        if len(nodes) < 2:
            return {"error": "Minimum 2 nodes required. Add more via POST /api/nodes"}
        # Global cleanup first
        subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        results = []
        for nid, n in nodes.items():
            try:
                n.start(cleanup=False, startup_wait=startup_wait)
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

    @app.post("/api/reset")
    async def reset_all():
        """Clear node, engine, scenario, and module state for a fresh topology load."""
        await stop_all()
        nodes.clear()
        engines.clear()
        node_modules.clear()
        node_module_status.clear()
        scenario_mgr.stop()
        scenario_mgr.events = []
        scenario_mgr.active_links.clear()
        scenario_mgr.active_link_types.clear()
        scenario_mgr.active_movements.clear()
        scenario_mgr.node_positions = {}
        scenario_mgr.current_time_relative = 0.0
        scenario_mgr.scenario_name = "Unnamed Scenario"
        scenario_mgr.wlan_nodes = []
        scenario_mgr.wlan_range = 200.0
        scenario_mgr.wlan_rate = 500000
        scenario_mgr.wlan_owlt = 1
        bundle_registry.clear()
        reset_dashboard_metrics()
        global current_briefing
        current_briefing = {}
        await broadcast({"type": "scenario_loaded", "count": 0, "briefing": current_briefing, "scenario_links": [], "node_positions": {}})
        return {"status": "reset"}

    @app.get("/api/nodes")
    async def list_nodes():
        return [n.status() for n in nodes.values()]

    @app.post("/api/nodes/{node_id}/stop")
    async def stop_node(node_id: int):
        node = nodes.get(node_id)
        if not node:
            return {"error": f"Node {node_id} not found"}
        try:
            node.stop()
        finally:
            engines.pop(node_id, None)
        await broadcast({"type": "node_stopped", "node_id": node_id})
        return {"status": "stopped", "node_id": node_id}

    @app.post("/api/nodes/{node_id}/start")
    async def start_node(node_id: int, startup_wait: float = 6.0):
        node = nodes.get(node_id)
        if not node:
            return {"error": f"Node {node_id} not found"}
        try:
            node.start(cleanup=False, startup_wait=startup_wait)
            eng = EmionEngine(node_id, base_dir=EMION_BASE_DIR)
            eng.attach()
            engines[node_id] = eng
        except Exception as exc:
            return {"error": str(exc)}
        await broadcast({"type": "node_started", "node_id": node_id})
        return {"status": "started", "node_id": node_id}

    # ── Links (auto-managed via connect_to) ───────────────────

    @app.get("/api/links")
    async def list_links():
        if scenario_mgr.is_running or scenario_mgr.active_links:
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
    async def send_bundle(from_node: int, to_node: int, payload: str = "EMION_TEST", ttl_seconds: int = 300, retransmission_count: int = 0, trace_id: str = ""):
        """Send a real BP bundle between ION nodes."""
        if from_node not in engines:
            return {"error": f"No engine for node {from_node}"}
        src = f"ipn:{from_node}.1"
        dst = f"ipn:{to_node}.1"
        data = payload.encode()
        if trace_id:
            data = f"__EMION_TRACE__{trace_id}\n".encode() + data
        try:
            engines[from_node].send(src, dst, data)
        except Exception as e:
            return {"error": str(e)}

        module_results, route_plan, bundle_features = process_bundle_pipeline(
            from_node,
            to_node,
            data,
            ttl_seconds=ttl_seconds,
            retransmission_count=retransmission_count,
        )
        send_ts = time.time()
        if trace_id:
            bundle_registry[trace_id] = {
                "trace_id": trace_id,
                "from_node": from_node,
                "to_node": to_node,
                "payload": payload,
                "payload_size": len(payload.encode()),
                "wire_size": len(data),
                "send_ts": send_ts,
                "status": "sent",
                "route_plan": route_plan,
                "bundle_features": bundle_features,
            }
        dashboard_metrics["bundle_sent_count"] += 1
        dashboard_metrics["bundle_bytes_sent"] += len(data)

        evt = {"type": "bundle_sent", "from": from_node, "to": to_node,
               "src": src, "dst": dst, "size": len(data), "payload_size": len(payload.encode()), "ts": send_ts,
               "trace_id": trace_id or None, "modules": module_results, "route_plan": route_plan,
               "bundle_features": bundle_features}
        event_log.append(evt)
        await broadcast(evt)
        return evt

    @app.post("/api/receive")
    async def receive_bundle(node_id: int, eid: str = "", timeout: int = 10):
        """Receive a bundle from a node endpoint and compute delivery metrics when tracked."""
        if node_id not in engines:
            return {"error": f"No engine for node {node_id}"}

        endpoint = eid or f"ipn:{node_id}.1"
        started = time.time()
        data = engines[node_id].receive(endpoint, timeout=timeout)
        if not data:
            dashboard_metrics["bundle_timeout_count"] += 1
            return {
                "status": "timeout",
                "node_id": node_id,
                "eid": endpoint,
                "waited_s": round(time.time() - started, 3),
            }

        received_ts = time.time()
        trace_id, unwrapped = _extract_trace_id_and_payload(data)
        result = {
            "status": "received",
            "node_id": node_id,
            "eid": endpoint,
            "size": len(data),
            "payload_size": len(unwrapped),
            "payload_text": unwrapped.decode("utf-8", errors="replace"),
            "payload_hex": unwrapped.hex(),
            "trace_id": trace_id,
            "received_ts": received_ts,
        }
        dashboard_metrics["bundle_received_count"] += 1
        dashboard_metrics["bundle_bytes_received"] += len(data)

        if trace_id and trace_id in bundle_registry:
            record = bundle_registry[trace_id]
            delivery_latency_ms = (received_ts - record["send_ts"]) * 1000.0
            record.update({
                "status": "received",
                "received_ts": received_ts,
                "delivery_latency_ms": delivery_latency_ms,
            })
            dashboard_metrics["delivery_latencies_ms"].append(delivery_latency_ms)
            result["delivery_latency_ms"] = round(delivery_latency_ms, 3)
            result["from_node"] = record["from_node"]
            result["to_node"] = record["to_node"]
            result["bundle_features"] = record.get("bundle_features", {})
        evt = {"type": "bundle_received", **result}
        event_log.append(evt)
        await broadcast(evt)
        return result

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

    @app.post("/api/modules/connect")
    async def attach_module_legacy(url: str, name: str = "", module_type: str = "anomaly", node_id: Optional[int] = None):
        """Backward-compatible alias for older clients and tests."""
        target_node = node_id
        if target_node is None:
            if not nodes:
                return {"error": "Register at least one node before attaching a module"}
            target_node = sorted(nodes.keys())[0]
        return await attach_module(target_node, url=url, name=name, module_type=module_type)

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

    @app.get("/api/metrics")
    async def get_metrics():
        return get_dashboard_metrics()

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.append(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            if ws in ws_clients:
                ws_clients.remove(ws)

    return app


async def telemetry_loop():
    """Background task to broadcast live telemetry and auto-feed modules."""
    while True:
        await asyncio.sleep(3)

        telemetry_data = []
        for nid, n in nodes.items():
            if n.is_running:
                telem = await asyncio.to_thread(n.get_system_telemetry)
                telemetry_data.append(telem)
                # Auto-feed: send node telemetry to all attached modules
                for mod in node_modules.get(nid, []):
                    try:
                        t0 = time.perf_counter()
                        result = await asyncio.to_thread(
                            mod.analyze,
                            json.dumps(telem).encode(),
                            {"source": "auto_feed", "node_id": nid, "type": "telemetry"},
                        )
                        latency_ms = (time.perf_counter() - t0) * 1000.0
                        if isinstance(result, dict):
                            result.setdefault("inference_latency_ms", round(latency_ms, 3))
                        dashboard_metrics["module_auto_feed_latencies_ms"].append(latency_ms)
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
                    "score": score,
                    "inference_latency_ms": result.get("inference_latency_ms", 0.0) if isinstance(result, dict) else 0.0,
                }

        if ws_clients and (telemetry_data or scenario_mgr.is_running or scenario_mgr.events):
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
    data.setdefault("server_ts", time.time())
    msg = json.dumps(data, default=str)
    msg_type = data.get("type", "unknown")
    dashboard_metrics["broadcast_counts"][msg_type] += 1
    if msg_type == "telemetry_update":
        dashboard_metrics["telemetry_message_count"] += 1
        dashboard_metrics["telemetry_bytes"] += len(msg.encode("utf-8"))
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

"""
Emion Scenario Engine - Manages time-based connectivity events for ION-DTN.
Allows simulation of orbital passes, light-delays, and link disruptions.
"""

import time
import json
import threading
import math
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from emion.pyion import mgmt

class ScenarioEvent:
    """Represents a single connectivity event in a simulation."""
    def __init__(self, timestamp: float, action: str, args: List[Any]):
        self.timestamp = timestamp  # Relative seconds from simulation start
        self.action = action        # add_contact, delete_contact, add_range, delete_range
        self.args = args
        self.executed = False

class ScenarioManager:
    """Orchestrates the execution of a DTN connectivity scenario."""
    
    def __init__(self):
        self.events: List[ScenarioEvent] = []
        self.is_running = False
        self.start_time: Optional[float] = None
        self._thread: Optional[threading.Thread] = None
        self.current_time_relative = 0.0
        self.active_links: set = set()
        self.active_link_types: Dict[tuple, str] = {}
        self.node_positions: Dict[int, Dict[str, float]] = {}
        self.active_movements: Dict[int, Dict[str, float]] = {}
        self.scenario_name = "Unnamed Scenario"
        self.wlan_nodes: List[int] = []
        self.wlan_range = 200.0

    def load_scenario(self, data: Union[List[Dict[str, Any]], Dict[str, Any]]):
        """Load scenario events and configuration from a structure."""
        self.events = []
        self.active_links.clear()
        self.active_link_types.clear()
        self.active_movements.clear()
        self.current_time_relative = 0.0
        self.scenario_name = data.get("name", "Unnamed Scenario") if isinstance(data, dict) else "Ad-hoc Scenario"
        
        self.wlan_nodes = data.get("wlan_nodes", []) if isinstance(data, dict) else []
        self.wlan_range = data.get("wlan_range", 200.0) if isinstance(data, dict) else 200.0
        
        events_list = data.get("events", []) if isinstance(data, dict) else data
        for item in events_list:
            event = ScenarioEvent(
                timestamp=item.get("time", 0.0),
                action=item.get("action", ""),
                args=item.get("args", [])
            )
            self.events.append(event)
        # Sort events by time
        self.events.sort(key=lambda x: x.timestamp)
        print(f"[Scenario] Loaded {len(self.events)} events. WLAN Nodes: {self.wlan_nodes} (Range: {self.wlan_range})")

    def start(self):
        """Start the simulation clock."""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = time.time()
        for e in self.events:
            e.executed = False
            
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("[Scenario] Simulation started.")

    def stop(self):
        """Stop the simulation clock."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.active_links.clear()
        self.active_link_types.clear()
        self.active_movements.clear()
        print("[Scenario] Simulation stopped.")

    def _run_loop(self):
        """Main simulation loop."""
        while self.is_running:
            self.current_time_relative = time.time() - self.start_time
            self._update_movements()
            
            # Find and execute pending events
            for event in self.events:
                if not event.executed and event.timestamp <= self.current_time_relative:
                    self._execute_event(event)
                    event.executed = True
            
            # Exact CORE-GUI logic: Math.hypot() spatial distance link evaluation
            if self.wlan_nodes:
                self._evaluate_spatial_links()
            
            # Check if all events are finished and WLAN evaluation isn't required anymore
            if all(e.executed for e in self.events) and not self.wlan_nodes:
                print("[Scenario] All events executed.")
                self.is_running = False
                break
                
            time.sleep(0.5)

    def _update_movements(self):
        completed = []
        for node_id, movement in self.active_movements.items():
            elapsed = max(0.0, self.current_time_relative - movement["start_time"])
            duration = max(movement["duration"], 0.001)
            progress = min(1.0, elapsed / duration)
            x = movement["from_x"] + (movement["to_x"] - movement["from_x"]) * progress
            y = movement["from_y"] + (movement["to_y"] - movement["from_y"]) * progress
            self.node_positions[node_id] = {"x": x, "y": y}
            if progress >= 1.0:
                completed.append(node_id)
        for node_id in completed:
            self.active_movements.pop(node_id, None)

    def _dispatch_ionadmin(self, cmd: str):
        """Helper to send a raw ionadmin command to all tracked node directories."""
        import os, subprocess
        for ndir in getattr(self, "node_dirs", []):
            if os.path.exists(ndir):
                env = os.environ.copy()
                node_id = os.path.basename(ndir)
                env["ION_NODE_NUMBER"] = node_id
                env.pop("ION_NODE_LIST_DIR", None)
                subprocess.run(
                    ["ionadmin"], 
                    input=cmd, 
                    text=True, 
                    cwd=ndir,
                    env=env,
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )

    def _evaluate_spatial_links(self):
        """Native CORE-GUI Basic Range Mobility Check."""
        for i in range(len(self.wlan_nodes)):
            for j in range(i + 1, len(self.wlan_nodes)):
                n1 = self.wlan_nodes[i]
                n2 = self.wlan_nodes[j]
                
                # We need positions for both nodes
                if n1 in self.node_positions and n2 in self.node_positions:
                    p1 = self.node_positions[n1]
                    p2 = self.node_positions[n2]
                    dist = math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"])
                    
                    link = tuple(sorted([n1, n2]))
                    is_connected = link in self.active_links
                    
                    if dist <= self.wlan_range and not is_connected:
                        self._dispatch_ionadmin(f"a contact +0 +3600 {n1} {n2} 500000\n")
                        self._dispatch_ionadmin(f"a contact +0 +3600 {n2} {n1} 500000\n")
                        self._dispatch_ionadmin(f"a range +0 +3600 {n1} {n2} 1\n")
                        self._dispatch_ionadmin(f"a range +0 +3600 {n2} {n1} 1\n")
                        self.active_links.add(link)
                        self.active_link_types[link] = "wlan"
                        msg = f"WLAN_UP: d={dist:.1f} <= {self.wlan_range} ({n1} <-> {n2})"
                        print(f"[Scenario] {msg}")
                        if hasattr(self, 'log_callback') and self.log_callback:
                            self.log_callback(msg, self.current_time_relative)
                            
                    elif dist > self.wlan_range and is_connected:
                        self._dispatch_ionadmin(f"d contact +0 {n1} {n2}\n")
                        self._dispatch_ionadmin(f"d contact +0 {n2} {n1}\n")
                        self.active_links.discard(link)
                        self.active_link_types.pop(link, None)
                        msg = f"WLAN_DOWN: d={dist:.1f} > {self.wlan_range} ({n1} <-/-> {n2})"
                        print(f"[Scenario] {msg}")
                        if hasattr(self, 'log_callback') and self.log_callback:
                            self.log_callback(msg, self.current_time_relative)

    def set_nodes(self, node_dirs: List[str]):
        self.node_dirs = node_dirs

    def _execute_event(self, event: ScenarioEvent):
        """Dispatch event via ionadmin to all nodes."""
        msg_text = f"Executing {event.action} {event.args}"
        print(f"[Scenario] @ {event.timestamp:.2f}s: {msg_text}")
        if hasattr(self, 'log_callback') and self.log_callback:
            self.log_callback(msg_text, event.timestamp)
        try:
            cmd = ""
            if event.action == "add_contact":
                # args: [from_node, to_node, tstart, tend, rate, confidence, announce]
                # or    [region_nbr, from_node, to_node, tstart, tend, rate, confidence, announce]
                if len(event.args) == 7:
                    from_node, to_node, tstart, tend, rate, conf, announce = event.args
                else:
                    region, from_node, to_node, tstart, tend, rate, conf, announce = event.args
                cmd = f"a contact {tstart} {tend} {from_node} {to_node} {rate}\n"
                link = tuple(sorted([from_node, to_node]))
                self.active_links.add(link)
                self.active_link_types[link] = "scheduled"
            elif event.action == "delete_contact":
                # args: [from_node, to_node, tstart, announce]
                # or    [region_nbr, from_node, to_node, tstart, announce]
                if len(event.args) == 4:
                    from_node, to_node, tstart, announce = event.args
                else:
                    region, from_node, to_node, tstart, announce = event.args
                cmd = f"d contact {tstart} {from_node} {to_node}\n"
                link = tuple(sorted([from_node, to_node]))
                self.active_links.discard(link)
                self.active_link_types.pop(link, None)
            elif event.action == "add_range":
                # args: [from_node, to_node, tstart, tend, owlt, announce]
                from_node, to_node, tstart, tend, owlt, announce = event.args
                cmd = f"a range {tstart} {tend} {from_node} {to_node} {owlt}\n"
            elif event.action == "delete_range":
                # args: [from_node, to_node, tstart, announce]
                from_node, to_node, tstart, announce = event.args
                cmd = f"d range {tstart} {from_node} {to_node}\n"
            elif event.action == "set_position":
                node_id, x, y = event.args
                self.node_positions[node_id] = {"x": x, "y": y}
                # Purely graphical, no CMD dispatched.
            elif event.action == "move_linear":
                node_id, from_x, from_y, to_x, to_y, duration = event.args
                self.node_positions[node_id] = {"x": from_x, "y": from_y}
                self.active_movements[node_id] = {
                    "start_time": event.timestamp,
                    "from_x": from_x,
                    "from_y": from_y,
                    "to_x": to_x,
                    "to_y": to_y,
                    "duration": duration,
                }
            else:
                print(f"[Scenario] Warning: Unknown action {event.action}")
                return
            if cmd:
                self._dispatch_ionadmin(cmd)
        except Exception as e:
            print(f"[Scenario] Error executing {event.action}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return the current progression of the simulation."""
        executed_events = sum(1 for e in self.events if e.executed)
        total_events = len(self.events)
        return {
            "name": self.scenario_name,
            "is_running": self.is_running,
            "elapsed": round(self.current_time_relative, 2),
            "total_events": total_events,
            "executed_events": executed_events,
            "pending_events": max(total_events - executed_events, 0),
            "progress_pct": round((executed_events / total_events) * 100, 1) if total_events else 0.0
        }

    def get_active_links(self) -> List[Dict[str, Any]]:
        return [
            {"from": l[0], "to": l[1], "kind": self.active_link_types.get(l, "unknown")}
            for l in sorted(self.active_links)
        ]

    def get_telemetry(self) -> Dict[str, Any]:
        executed_events = sum(1 for e in self.events if e.executed)
        pending_events = [e for e in self.events if not e.executed]
        next_event = pending_events[0] if pending_events else None
        moving_nodes = []
        for node_id, movement in self.active_movements.items():
            dx = movement["to_x"] - movement["from_x"]
            dy = movement["to_y"] - movement["from_y"]
            duration = max(movement["duration"], 0.001)
            moving_nodes.append({
                "node_id": node_id,
                "speed": round(math.hypot(dx, dy) / duration, 2),
                "eta": round(max((movement["start_time"] + duration) - self.current_time_relative, 0.0), 2),
                "destination": {"x": movement["to_x"], "y": movement["to_y"]},
            })

        wired_links = sum(1 for kind in self.active_link_types.values() if kind == "scheduled")
        wlan_links = sum(1 for kind in self.active_link_types.values() if kind == "wlan")

        return {
            "name": self.scenario_name,
            "is_running": self.is_running,
            "elapsed": round(self.current_time_relative, 2),
            "executed_events": executed_events,
            "total_events": len(self.events),
            "pending_events": max(len(self.events) - executed_events, 0),
            "progress_pct": round((executed_events / len(self.events)) * 100, 1) if self.events else 0.0,
            "next_event_time": round(next_event.timestamp, 2) if next_event else None,
            "next_event_action": next_event.action if next_event else None,
            "active_link_count": len(self.active_links),
            "wired_link_count": wired_links,
            "wlan_link_count": wlan_links,
            "moving_node_count": len(self.active_movements),
            "tracked_node_count": len(self.node_positions),
            "wlan_node_count": len(self.wlan_nodes),
            "wlan_range": self.wlan_range,
            "moving_nodes": moving_nodes,
        }

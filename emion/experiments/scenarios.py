"""Scenario generators used by the automated experiment runner."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from emion.core.mars_import import parse_core_xml_scenario


def _circle_positions(node_count: int, radius: float = 280.0, center_x: float = 450.0, center_y: float = 280.0) -> Dict[int, Tuple[float, float]]:
    positions = {}
    for idx in range(node_count):
        angle = (idx / max(node_count, 1)) * 2 * math.pi
        positions[idx + 1] = (
            round(center_x + radius * math.cos(angle), 3),
            round(center_y + radius * math.sin(angle), 3),
        )
    return positions


def _grid_positions(node_count: int, cols: int = 4, spacing: float = 140.0) -> Dict[int, Tuple[float, float]]:
    positions = {}
    for idx in range(node_count):
        row = idx // cols
        col = idx % cols
        positions[idx + 1] = (
            round(140.0 + col * spacing, 3),
            round(120.0 + row * spacing, 3),
        )
    return positions


def _leo_geo_positions(node_count: int) -> Dict[int, Tuple[float, float]]:
    """Place 16 LEO nodes in a ring and up to 4 GEO relay nodes outside it."""
    if node_count < 8:
        raise ValueError("leo_geo topology requires at least 8 nodes")

    leo_count = min(node_count - 4, 16) if node_count >= 12 else node_count - 2
    geo_count = node_count - leo_count
    positions = {}
    positions.update(_circle_positions(leo_count, radius=240.0, center_x=480.0, center_y=320.0))
    geo_radius = 380.0
    for idx in range(geo_count):
        angle = ((idx + 0.5) / max(geo_count, 1)) * 2 * math.pi
        node_id = leo_count + idx + 1
        positions[node_id] = (
            round(480.0 + geo_radius * math.cos(angle), 3),
            round(320.0 + geo_radius * math.sin(angle), 3),
        )
    return positions


def _edge_list(topology: str, node_count: int) -> List[Tuple[int, int]]:
    if topology == "line":
        return [(idx, idx + 1) for idx in range(1, node_count)]
    if topology == "ring":
        edges = [(idx, idx + 1) for idx in range(1, node_count)]
        if node_count > 2:
            edges.append((node_count, 1))
        return edges
    if topology == "star":
        return [(1, idx) for idx in range(2, node_count + 1)]
    if topology == "mesh":
        return [(left, right) for left in range(1, node_count + 1) for right in range(left + 1, node_count + 1)]
    if topology == "leo_geo":
        if node_count < 8:
            raise ValueError("leo_geo topology requires at least 8 nodes")
        leo_count = min(node_count - 4, 16) if node_count >= 12 else node_count - 2
        geo_nodes = list(range(leo_count + 1, node_count + 1))
        edges = [(idx, idx + 1) for idx in range(1, leo_count)]
        edges.append((leo_count, 1))
        if len(geo_nodes) > 1:
            edges.extend((geo_nodes[idx], geo_nodes[(idx + 1) % len(geo_nodes)]) for idx in range(len(geo_nodes)))
        for idx in range(1, leo_count + 1):
            geo = geo_nodes[(idx - 1) % len(geo_nodes)]
            edges.append((idx, geo))
        return edges
    raise ValueError(f"Unsupported topology: {topology}")


def _add_bidirectional_contact(events: List[dict], left: int, right: int, *, rate: int, owlt: int, start: str = "+0", end: str = "+3600") -> None:
    events.extend([
        {"time": 0.0, "action": "add_contact", "args": [left, right, start, end, rate, 1.0, 1]},
        {"time": 0.0, "action": "add_contact", "args": [right, left, start, end, rate, 1.0, 1]},
        {"time": 0.0, "action": "add_range", "args": [left, right, start, end, owlt, 1]},
        {"time": 0.0, "action": "add_range", "args": [right, left, start, end, owlt, 1]},
    ])


def _delete_bidirectional_contact(events: List[dict], left: int, right: int, *, at_time: float, start: str = "+0") -> None:
    events.extend([
        {"time": at_time, "action": "delete_contact", "args": [left, right, start, 1]},
        {"time": at_time, "action": "delete_contact", "args": [right, left, start, 1]},
        {"time": at_time, "action": "delete_range", "args": [left, right, start, 1]},
        {"time": at_time, "action": "delete_range", "args": [right, left, start, 1]},
    ])


def _apply_disruption(events: List[dict], topology: str, node_count: int, disruption: str, *, bandwidth_bps: int, owlt: int) -> List[dict]:
    runtime_actions: List[dict] = []
    if disruption == "none":
        return runtime_actions

    if topology == "ring":
        critical_edge = (1, node_count)
    elif topology == "star":
        critical_edge = (1, max(2, node_count // 2 + 1))
    else:
        critical_edge = (max(1, node_count // 2), max(2, node_count // 2 + 1))

    if disruption == "sudden_contact_failure":
        _delete_bidirectional_contact(events, *critical_edge, at_time=10.0)
    elif disruption == "intermittent_connectivity":
        _delete_bidirectional_contact(events, *critical_edge, at_time=10.0)
        events.extend([
            {"time": 20.0, "action": "add_contact", "args": [critical_edge[0], critical_edge[1], "+0", "+3600", bandwidth_bps, 1.0, 1]},
            {"time": 20.0, "action": "add_contact", "args": [critical_edge[1], critical_edge[0], "+0", "+3600", bandwidth_bps, 1.0, 1]},
            {"time": 20.0, "action": "add_range", "args": [critical_edge[0], critical_edge[1], "+0", "+3600", owlt, 1]},
            {"time": 20.0, "action": "add_range", "args": [critical_edge[1], critical_edge[0], "+0", "+3600", owlt, 1]},
        ])
    elif disruption == "bandwidth_degradation":
        _delete_bidirectional_contact(events, *critical_edge, at_time=10.0)
        degraded_rate = max(int(bandwidth_bps * 0.25), 1)
        events.extend([
            {"time": 11.0, "action": "add_contact", "args": [critical_edge[0], critical_edge[1], "+0", "+3600", degraded_rate, 1.0, 1]},
            {"time": 11.0, "action": "add_contact", "args": [critical_edge[1], critical_edge[0], "+0", "+3600", degraded_rate, 1.0, 1]},
            {"time": 11.0, "action": "add_range", "args": [critical_edge[0], critical_edge[1], "+0", "+3600", owlt, 1]},
            {"time": 11.0, "action": "add_range", "args": [critical_edge[1], critical_edge[0], "+0", "+3600", owlt, 1]},
        ])
    elif disruption == "node_crash":
        runtime_actions.append({"time": 10.0, "type": "stop_node", "node_id": critical_edge[1]})
        runtime_actions.append({"time": 20.0, "type": "start_node", "node_id": critical_edge[1]})
    elif disruption == "packet_corruption":
        runtime_actions.append({"time": 0.0, "type": "mark_corrupted_bundle", "ratio": 0.2})
    else:
        raise ValueError(f"Unsupported disruption: {disruption}")
    return runtime_actions


def generate_scenario(
    *,
    topology: str,
    node_count: int,
    bandwidth_bps: int = 500000,
    owlt: int = 1,
    disruption: str = "none",
    layout: str = "circle",
    name: str | None = None,
) -> dict:
    if node_count < 2:
        raise ValueError("node_count must be at least 2")

    if topology == "leo_geo":
        positions = _leo_geo_positions(node_count)
        layout = "leo_geo"
    else:
        positions = _circle_positions(node_count) if layout == "circle" else _grid_positions(node_count)
    events: List[dict] = []
    for node_id, (x, y) in positions.items():
        events.append({"time": 0.0, "action": "set_position", "args": [node_id, x, y]})

    for left, right in _edge_list(topology, node_count):
        _add_bidirectional_contact(events, left, right, rate=bandwidth_bps, owlt=owlt)

    runtime_actions = _apply_disruption(events, topology, node_count, disruption, bandwidth_bps=bandwidth_bps, owlt=owlt)
    return {
        "name": name or f"{topology}_{node_count}_{disruption}",
        "topology": topology,
        "node_count": node_count,
        "layout": layout,
        "runtime_actions": runtime_actions,
        "events": sorted(events, key=lambda item: (item.get("time", 0.0), item.get("action", ""))),
    }


def load_actual_ion_schedule(xml_path: str | Path) -> dict:
    """Load an actual ION-backed CORE/Mars scenario into EmION format."""
    return parse_core_xml_scenario(Path(xml_path))


def materialize_scenarios(
    output_dir: str | Path,
    *,
    topologies: Iterable[str],
    node_counts: Iterable[int],
    disruptions: Iterable[str],
    bandwidth_bps: int = 500000,
    owlt: int = 1,
) -> List[Path]:
    import json

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for topology in topologies:
        for node_count in node_counts:
            for disruption in disruptions:
                scenario = generate_scenario(
                    topology=topology,
                    node_count=node_count,
                    bandwidth_bps=bandwidth_bps,
                    owlt=owlt,
                    disruption=disruption,
                )
                path = output_path / f"{topology}_{node_count}_{disruption}.json"
                path.write_text(json.dumps(scenario, indent=2))
                written.append(path)
    return written

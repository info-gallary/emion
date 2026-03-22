"""
Helpers for translating CORE's ion_mars XML + NS2 mobility into EmION scenarios.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _parse_ns2_segments(scen_path: Path) -> tuple[dict[int, tuple[float, float]], list[dict]]:
    initial_positions: dict[int, tuple[float, float]] = {}
    move_starts: dict[int, list[dict]] = {}

    set_re = re.compile(r"\$node_\((\d+)\) set ([XYZ])_ ([0-9.+-]+)")
    move_re = re.compile(
        r'\$ns_ at ([0-9.+-]+) "\$node_\((\d+)\) setdest ([0-9.+-]+) ([0-9.+-]+) ([0-9.+-]+)"'
    )

    with scen_path.open("r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            set_match = set_re.match(line)
            if set_match:
                node_id = int(set_match.group(1))
                axis = set_match.group(2)
                value = float(set_match.group(3))
                x, y = initial_positions.get(node_id, (0.0, 0.0))
                if axis == "X":
                    x = value
                elif axis == "Y":
                    y = value
                initial_positions[node_id] = (x, y)
                continue

            move_match = move_re.match(line)
            if move_match:
                start_time = float(move_match.group(1))
                node_id = int(move_match.group(2))
                dst_x = float(move_match.group(3))
                dst_y = float(move_match.group(4))
                duration = float(move_match.group(5))
                move_starts.setdefault(node_id, []).append(
                    {
                        "time": start_time,
                        "dst_x": dst_x,
                        "dst_y": dst_y,
                        "duration": duration,
                    }
                )

    events = []
    for node_id, moves in move_starts.items():
        curr_x, curr_y = initial_positions.get(node_id, (0.0, 0.0))
        for move in sorted(moves, key=lambda x: x["time"]):
            events.append(
                {
                    "time": move["time"],
                    "action": "move_linear",
                    "args": [
                        node_id,
                        curr_x,
                        curr_y,
                        move["dst_x"],
                        move["dst_y"],
                        move["duration"],
                    ],
                }
            )
            curr_x, curr_y = move["dst_x"], move["dst_y"]

    return initial_positions, events


def _extract_repeat_count(rcgen_path: Path) -> int:
    if not rcgen_path.exists():
        return 1
    match = re.search(r'numloops="(\d+)"', rcgen_path.read_text())
    return int(match.group(1)) if match else 1


def build_ion_mars_scenario(mars_xml_path: Path, loop_count: int | None = None) -> dict:
    tree = ET.parse(mars_xml_path)
    root = tree.getroot()

    events: list[dict] = []
    device_positions: dict[int, tuple[float, float]] = {}
    wlan_nodes: list[int] = []
    wlan_range = 200.0
    wireless_net_ids: set[int] = set()

    for network in root.findall("./networks/network"):
        if network.get("type") == "WIRELESS_LAN":
            wireless_net_ids.add(int(network.get("id")))

    for device in root.findall("./devices/device"):
        node_id = int(device.get("id"))
        pos = device.find("position")
        if pos is not None:
            x = float(pos.get("x", "0"))
            y = float(pos.get("y", "0"))
            device_positions[node_id] = (x, y)
            events.append({"time": 0.0, "action": "set_position", "args": [node_id, x, y]})

    for link in root.findall("./links/link"):
        node1 = int(link.get("node1"))
        node2 = int(link.get("node2"))
        if node1 in wireless_net_ids and node2 not in wireless_net_ids:
            wlan_nodes.append(node2)
            continue
        if node2 in wireless_net_ids and node1 not in wireless_net_ids:
            wlan_nodes.append(node1)
            continue

        # Wired CORE links are always present; reflect them as static ION contacts.
        events.extend(
            [
                {"time": 0.0, "action": "add_contact", "args": [node1, node2, "+0", "+4000000", 500000, 1.0, 1]},
                {"time": 0.0, "action": "add_contact", "args": [node2, node1, "+0", "+4000000", 500000, 1.0, 1]},
                {"time": 0.0, "action": "add_range", "args": [node1, node2, "+0", "+4000000", 1, 1]},
                {"time": 0.0, "action": "add_range", "args": [node2, node1, "+0", "+4000000", 1, 1]},
            ]
        )

    mobility = root.find("./mobility_configurations")
    scen_file: Path | None = None
    if mobility is not None:
        for config in mobility.findall("mobility_configuration"):
            model = config.get("model")
            if model == "basic_range":
                for entry in config.findall("configuration"):
                    if entry.get("name") == "range":
                        wlan_range = float(entry.get("value", "200"))
            elif model == "ns2script":
                for entry in config.findall("configuration"):
                    if entry.get("name") == "file":
                        scen_file = Path(entry.get("value"))

    if scen_file and scen_file.exists():
        repeat_count = loop_count if loop_count is not None else _extract_repeat_count(mars_xml_path.parent / "rcgen.sh")
        initial_positions, move_events = _parse_ns2_segments(scen_file)
        duration = max((event["time"] + event["args"][-1] for event in move_events), default=0.0)
        for node_id, (x, y) in initial_positions.items():
            if node_id not in device_positions:
                events.append({"time": 0.0, "action": "set_position", "args": [node_id, x, y]})
        for loop_index in range(repeat_count):
            offset = loop_index * duration
            for event in move_events:
                looped = dict(event)
                looped["time"] = event["time"] + offset
                looped["args"] = event["args"][:]
                events.append(looped)

    events.sort(key=lambda item: (item["time"], item["action"]))
    return {
        "name": "Original ion_mars Mobility (parsed from mars.xml)",
        "wlan_nodes": sorted(set(wlan_nodes)),
        "wlan_range": wlan_range,
        "events": events,
    }

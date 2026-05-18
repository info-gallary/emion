"""
Helpers for parsing any generic CORE XML topologies into EmION scenarios.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _to_number(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_support_file(xml_path: Path, raw_value: str | None) -> Path | None:
    if not raw_value:
        return None

    raw_path = Path(raw_value).expanduser()
    repo_root = Path(__file__).resolve().parents[2]
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append((xml_path.parent / raw_path).resolve())
    candidates.extend([
        (xml_path.parent / raw_path.name).resolve(),
        (xml_path.parent.parent / raw_path.name).resolve(),
        (repo_root / raw_path.name).resolve(),
        (repo_root / "examples" / raw_path.name).resolve(),
    ])

    for candidate in candidates:
        if candidate.exists():
            return candidate

    for search_root in (repo_root / "examples", repo_root):
        if search_root.exists():
            matches = list(search_root.rglob(raw_path.name))
            if matches:
                return matches[0]
    return None


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


def _build_contact_events(
    node1: int,
    node2: int,
    *,
    bandwidth: float,
    owlt: float,
    confidence: float = 1.0,
    start: str = "+0",
    end: str = "+4000000",
    bidirectional: bool = True,
) -> list[dict]:
    rate = max(int(bandwidth), 1)
    range_value = max(int(round(owlt)), 1)
    events = [
        {"time": 0.0, "action": "add_contact", "args": [node1, node2, start, end, rate, confidence, 1]},
        {"time": 0.0, "action": "add_range", "args": [node1, node2, start, end, range_value, 1]},
    ]
    if bidirectional:
        events.extend([
            {"time": 0.0, "action": "add_contact", "args": [node2, node1, start, end, rate, confidence, 1]},
            {"time": 0.0, "action": "add_range", "args": [node2, node1, start, end, range_value, 1]},
        ])
    return events


def _parse_core_style_xml(root: ET.Element, xml_path: Path, loop_count: int | None = None) -> dict:
    events: list[dict] = []
    device_positions: dict[int, tuple[float, float]] = {}
    wlan_nodes: list[int] = []
    wlan_range = 200.0
    wlan_rate = 54000000.0
    wlan_owlt = 1.0
    wireless_net_ids: set[int] = set()
    l2_devices: set[int] = set()  # Hubs/Switches
    all_nodes: set[int] = set()

    for network in root.findall("./networks/network"):
        net_id = network.get("id")
        if net_id is None:
            continue
        nid = int(net_id)
        net_type = network.get("type", "")
        if net_type == "WIRELESS_LAN":
            wireless_net_ids.add(nid)
        elif net_type in ("HUB", "SWITCH"):
            l2_devices.add(nid)

    for device in root.findall("./devices/device"):
        dev_id = device.get("id")
        if dev_id is None:
            continue
        node_id = int(dev_id)
        dtype = device.get("type", "").lower()

        if dtype in ("hub", "switch", "rj45", "tunnel", "ovs") or "switch" in device.get("name", "").lower():
            l2_devices.add(node_id)
            continue

        all_nodes.add(node_id)
        pos = device.find("position")
        if pos is not None:
            x = float(pos.get("x", "0"))
            y = float(pos.get("y", "0"))
            device_positions[node_id] = (x, y)

    # Fallback positions for nodes without coordinates (place in a circle)
    missing_pos = [nid for nid in all_nodes if nid not in device_positions]
    if missing_pos:
        for i, nid in enumerate(missing_pos):
            angle = (i / len(missing_pos)) * 2 * math.pi
            x = 500 + 300 * math.cos(angle)
            y = 375 + 300 * math.sin(angle)
            device_positions[nid] = (x, y)

    for node_id, (x, y) in device_positions.items():
        if node_id in all_nodes:
            events.append({"time": 0.0, "action": "set_position", "args": [node_id, x, y]})

    for link in root.findall("./links/link"):
        n1_str, n2_str = link.get("node1"), link.get("node2")
        if not n1_str or not n2_str:
            continue
        node1, node2 = int(n1_str), int(n2_str)

        # WLAN connections
        if node1 in wireless_net_ids and node2 in all_nodes:
            wlan_nodes.append(node2)
            continue
        if node2 in wireless_net_ids and node1 in all_nodes:
            wlan_nodes.append(node1)
            continue

        # Ignore L2 interconnects in ION layer
        if node1 in l2_devices or node2 in l2_devices or node1 in wireless_net_ids or node2 in wireless_net_ids:
            continue

        options = link.find("options")
        bandwidth = _to_number(options.get("bandwidth") if options is not None else None, 500000.0)
        delay = _to_number(options.get("delay") if options is not None else None, 1.0)
        loss = _to_number(options.get("loss") if options is not None else None, 0.0)
        if loss > 1.0:
            confidence = max(0.0, 1.0 - (loss / 100.0))
        else:
            confidence = max(0.0, 1.0 - loss)
        bidirectional = not _to_bool(options.get("unidirectional") if options is not None else None, False)

        # Wired CORE links
        events.extend(
            _build_contact_events(
                node1,
                node2,
                bandwidth=bandwidth,
                owlt=delay,
                confidence=confidence,
                bidirectional=bidirectional,
            )
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
                    elif entry.get("name") == "bandwidth":
                        wlan_rate = _to_number(entry.get("value"), wlan_rate)
                    elif entry.get("name") == "delay":
                        wlan_owlt = max(_to_number(entry.get("value"), wlan_owlt), 1.0)
            elif model == "ns2script":
                for entry in config.findall("configuration"):
                    if entry.get("name") == "file":
                        scen_file = _resolve_support_file(xml_path, entry.get("value"))

    if scen_file and scen_file.exists():
        repeat_count = loop_count if loop_count is not None else _extract_repeat_count(xml_path.parent / "rcgen.sh")
        initial_positions, move_events = _parse_ns2_segments(scen_file)
        duration = max((event["time"] + event["args"][-1] for event in move_events), default=0.01)
        for node_id, (x, y) in initial_positions.items():
            if node_id in all_nodes:
                # Update initial position if NS2 script defines it
                device_positions[node_id] = (x, y)
                # Filter old set_position events for this node
                events = [e for e in events if not (e["action"] == "set_position" and e["args"][0] == node_id)]
                events.append({"time": 0.0, "action": "set_position", "args": [node_id, x, y]})

        for loop_index in range(repeat_count):
            offset = loop_index * duration
            for event in move_events:
                looped = dict(event)
                looped["time"] = event["time"] + offset
                looped["args"] = event["args"][:]
                events.append(looped)

    events.sort(key=lambda item: (item["time"], item["action"]))
    base_name = xml_path.stem
    return {
        "name": f"{base_name} Topology (Extracted)",
        "wlan_nodes": sorted(set(wlan_nodes)),
        "wlan_range": wlan_range,
        "wlan_rate": int(max(wlan_rate, 1.0)),
        "wlan_owlt": int(max(round(wlan_owlt), 1.0)),
        "events": events,
    }


def _parse_custom_event_xml(root: ET.Element, xml_path: Path) -> dict:
    scenario_name = root.get("name") or f"{xml_path.stem} Custom Scenario"
    wlan_range = _to_number(root.get("wlan_range"), 200.0)
    wlan_rate = int(max(_to_number(root.get("wlan_rate"), 54000000.0), 1.0))
    wlan_owlt = int(max(round(_to_number(root.get("wlan_owlt"), 1.0)), 1.0))
    wlan_nodes: set[int] = set()
    events: list[dict] = []
    node_positions: dict[int, tuple[float, float]] = {}

    for node in root.findall(".//nodes/node"):
        node_id = node.get("id")
        if node_id is None:
            continue
        nid = int(node_id)
        x = _to_number(node.get("x"), _to_number(node.get("from_x"), 0.0))
        y = _to_number(node.get("y"), _to_number(node.get("from_y"), 0.0))
        node_positions[nid] = (x, y)
        if _to_bool(node.get("wlan")):
            wlan_nodes.add(nid)

    for member in root.findall(".//wlan/member"):
        node_id = member.get("node") or member.get("id")
        if node_id is not None:
            wlan_nodes.add(int(node_id))

    for nid, (x, y) in node_positions.items():
        events.append({"time": 0.0, "action": "set_position", "args": [nid, x, y]})

    for link in root.findall(".//links/link"):
        from_attr = link.get("from") or link.get("node1")
        to_attr = link.get("to") or link.get("node2")
        if not from_attr or not to_attr:
            continue

        node1 = int(from_attr)
        node2 = int(to_attr)
        kind = (link.get("kind") or "scheduled").strip().lower()
        bidirectional = not _to_bool(link.get("unidirectional"), False)
        bandwidth = _to_number(link.get("rate") or link.get("bandwidth"), 500000.0)
        owlt = _to_number(link.get("owlt") or link.get("delay"), 1.0)
        confidence = _to_number(link.get("confidence"), 1.0)

        if kind == "wlan":
            wlan_nodes.update({node1, node2})
            continue

        events.extend(
            _build_contact_events(
                node1,
                node2,
                bandwidth=bandwidth,
                owlt=owlt,
                confidence=confidence,
                start=link.get("start", "+0"),
                end=link.get("end", "+4000000"),
                bidirectional=bidirectional,
            )
        )

    event_nodes = root.findall("./events/event") or root.findall("./event")
    for event in event_nodes:
        action = (event.get("action") or "").strip()
        timestamp = _to_number(event.get("time"), 0.0)
        if not action:
            continue

        if action == "set_position":
            node_id = int(event.get("node") or event.get("node_id"))
            x = _to_number(event.get("x"))
            y = _to_number(event.get("y"))
            events.append({"time": timestamp, "action": action, "args": [node_id, x, y]})
            continue

        if action == "move_linear":
            node_id = int(event.get("node") or event.get("node_id"))
            from_x = _to_number(event.get("from_x"))
            from_y = _to_number(event.get("from_y"))
            to_x = _to_number(event.get("to_x"))
            to_y = _to_number(event.get("to_y"))
            duration = _to_number(event.get("duration"), 1.0)
            events.append({
                "time": timestamp,
                "action": action,
                "args": [node_id, from_x, from_y, to_x, to_y, duration],
            })
            continue

        if action in {"add_contact", "delete_contact", "add_range", "delete_range"}:
            from_node = int(event.get("from") or event.get("node1"))
            to_node = int(event.get("to") or event.get("node2"))
            if action == "add_contact":
                args = [
                    from_node,
                    to_node,
                    event.get("start", "+0"),
                    event.get("end", "+4000000"),
                    int(max(_to_number(event.get("rate") or event.get("bandwidth"), 500000.0), 1.0)),
                    _to_number(event.get("confidence"), 1.0),
                    1,
                ]
            elif action == "delete_contact":
                args = [from_node, to_node, event.get("start", "+0"), 1]
            elif action == "add_range":
                args = [
                    from_node,
                    to_node,
                    event.get("start", "+0"),
                    event.get("end", "+4000000"),
                    int(max(round(_to_number(event.get("owlt") or event.get("delay"), 1.0)), 1.0)),
                    1,
                ]
            else:
                args = [from_node, to_node, event.get("start", "+0"), 1]
            events.append({"time": timestamp, "action": action, "args": args})

    events.sort(key=lambda item: (item["time"], item["action"]))
    return {
        "name": scenario_name,
        "wlan_nodes": sorted(wlan_nodes),
        "wlan_range": wlan_range,
        "wlan_rate": wlan_rate,
        "wlan_owlt": wlan_owlt,
        "events": events,
    }


def parse_core_xml_scenario(xml_path: Path, loop_count: int | None = None) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if root.find("./devices") is not None or root.find("./networks") is not None:
        return _parse_core_style_xml(root, xml_path, loop_count=loop_count)
    return _parse_custom_event_xml(root, xml_path)

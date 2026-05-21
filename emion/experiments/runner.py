"""Automated experiment runner for EmION."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from emion.experiments.scenarios import generate_scenario, load_actual_ion_schedule
from emion.dashboard.server import _extract_trace_id_and_payload

try:
    import websockets
except ImportError:  # pragma: no cover - optional runtime dependency
    websockets = None


@dataclass
class ExperimentCase:
    name: str
    topology: str
    node_count: int
    bundle_count: int
    bundle_size: int
    bundle_interval_s: float = 0.5
    startup_wait_s: float = 6.0
    warmup_s: float = 2.0
    receive_timeout_s: int = 12
    traffic_mode: str = "end_to_end"
    disruption: str = "none"
    bandwidth_bps: int = 500000
    owlt: int = 1
    dashboard_port: int = 8420
    attach_ml_module: bool = False
    scenario_source: str = "generated"
    scenario_path: str = ""
    telemetry_sample_s: float = 1.0


def _make_payload(size: int, *, index: int) -> str:
    prefix = f"bundle-{index:04d}:"
    if len(prefix) >= size:
        return prefix[:size]
    return prefix + ("X" * (size - len(prefix)))


def _traffic_pairs(case: ExperimentCase) -> List[Tuple[int, int]]:
    if case.traffic_mode == "end_to_end":
        return [(1, case.node_count)]
    if case.traffic_mode == "ring_pairs":
        return [(idx, idx + 1 if idx < case.node_count else 1) for idx in range(1, case.node_count + 1)]
    if case.traffic_mode == "fanout":
        return [(1, idx) for idx in range(2, case.node_count + 1)]
    raise ValueError(f"Unsupported traffic_mode: {case.traffic_mode}")


def _default_matrix() -> List[ExperimentCase]:
    cases: List[ExperimentCase] = []
    for node_count in (3, 5, 7):
        cases.append(
            ExperimentCase(
                name=f"scalability_star_{node_count}",
                topology="star",
                node_count=node_count,
                bundle_count=3,
                bundle_size=256,
                bundle_interval_s=0.5,
                startup_wait_s=6.0,
                traffic_mode="end_to_end",
            )
        )
    for rate_case, interval_s in (("rate_low", 1.5), ("rate_medium", 0.75), ("rate_high", 0.25)):
        cases.append(
            ExperimentCase(
                name=f"dashboard_latency_{rate_case}",
                topology="star",
                node_count=5,
                bundle_count=6,
                bundle_size=256,
                bundle_interval_s=interval_s,
                startup_wait_s=6.0,
                traffic_mode="end_to_end",
            )
        )
    for bundle_size in (128, 512, 1024):
        cases.append(
            ExperimentCase(
                name=f"throughput_size_{bundle_size}",
                topology="star",
                node_count=5,
                bundle_count=4,
                bundle_size=bundle_size,
                bundle_interval_s=0.5,
                startup_wait_s=6.0,
                traffic_mode="end_to_end",
            )
        )
    return cases


def _load_cases(config_path: Optional[str]) -> List[ExperimentCase]:
    if not config_path:
        return _default_matrix()

    payload = json.loads(Path(config_path).read_text())
    cases = []
    for raw_case in payload.get("cases", []):
        cases.append(ExperimentCase(**raw_case))
    return cases


def _wait_for_http(base_url: str, timeout_s: float = 30.0) -> None:
    started = time.time()
    while time.time() - started < timeout_s:
        try:
            resp = requests.get(f"{base_url}/", timeout=2)
            if resp.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Dashboard did not become ready at {base_url}")


class ResourceSampler(threading.Thread):
    def __init__(self, base_url: str, sample_interval_s: float, sink: List[dict], stop_event: threading.Event):
        super().__init__(daemon=True)
        self.base_url = base_url
        self.sample_interval_s = sample_interval_s
        self.sink = sink
        self.stop_event = stop_event

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                resp = requests.get(f"{self.base_url}/api/nodes", timeout=5)
                if resp.ok:
                    ts = time.time()
                    for node in resp.json():
                        resources = (node.get("telemetry") or {}).get("resources") or {}
                        self.sink.append({
                            "timestamp": ts,
                            "node_id": node.get("node_id"),
                            "cpu_percent": resources.get("cpu_percent", 0.0),
                            "rss_bytes": resources.get("rss_bytes", 0),
                            "process_count": resources.get("process_count", 0),
                        })
            except requests.RequestException:
                pass
            self.stop_event.wait(self.sample_interval_s)


class RuntimeActionScheduler(threading.Thread):
    def __init__(self, base_url: str, actions: Iterable[dict], startup_wait_s: float):
        super().__init__(daemon=True)
        self.base_url = base_url
        self.actions = sorted(actions, key=lambda item: item.get("time", 0.0))
        self.startup_wait_s = startup_wait_s
        self._stop_event = threading.Event()
        self._anchor = None

    def stop(self) -> None:
        self._stop_event.set()

    def arm(self, anchor_time: float) -> None:
        self._anchor = anchor_time

    def run(self) -> None:
        if self._anchor is None:
            return
        for action in self.actions:
            target_time = self._anchor + float(action.get("time", 0.0))
            while not self._stop_event.is_set() and time.time() < target_time:
                time.sleep(0.1)
            if self._stop_event.is_set():
                return
            action_type = action.get("type")
            node_id = action.get("node_id")
            try:
                if action_type == "stop_node":
                    requests.post(f"{self.base_url}/api/nodes/{node_id}/stop", timeout=10)
                elif action_type == "start_node":
                    requests.post(
                        f"{self.base_url}/api/nodes/{node_id}/start",
                        params={"startup_wait": self.startup_wait_s},
                        timeout=20,
                    )
            except requests.RequestException:
                continue


class TelemetryListener(threading.Thread):
    def __init__(self, ws_url: str, sink: List[dict], stop_event: threading.Event):
        super().__init__(daemon=True)
        self.ws_url = ws_url
        self.sink = sink
        self.stop_event = stop_event

    async def _listen(self) -> None:
        if websockets is None:
            return
        try:
            async with websockets.connect(self.ws_url, ping_interval=None) as websocket:
                while not self.stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    recv_ts = time.time()
                    event = json.loads(raw)
                    if event.get("type") == "telemetry_update":
                        self.sink.append({
                            "received_ts": recv_ts,
                            "server_ts": event.get("server_ts", recv_ts),
                            "latency_ms": round((recv_ts - float(event.get("server_ts", recv_ts))) * 1000.0, 3),
                            "payload_bytes": len(raw.encode("utf-8")),
                        })
        except Exception:
            return

    def run(self) -> None:
        asyncio.run(self._listen())


def _write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: List[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _write_svg_line_chart(path: Path, *, title: str, x_label: str, y_label: str, rows: List[Tuple[float, float]]) -> None:
    if not rows:
        path.write_text("")
        return
    width = 640
    height = 360
    padding = 50
    xs = [row[0] for row in rows]
    ys = [row[1] for row in rows]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_span = max(max_x - min_x, 1e-9)
    y_span = max(max_y - min_y, 1e-9)

    def sx(value: float) -> float:
        return padding + ((value - min_x) / x_span) * (width - 2 * padding)

    def sy(value: float) -> float:
        return height - padding - ((value - min_y) / y_span) * (height - 2 * padding)

    points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in rows)
    circles = "\n".join(
        f"<circle cx='{sx(x):.2f}' cy='{sy(y):.2f}' r='4' fill='#1d4ed8' />"
        f"<text x='{sx(x):.2f}' y='{sy(y) - 8:.2f}' font-size='10' text-anchor='middle'>{y:.3f}</text>"
        for x, y in rows
    )
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
<rect width='100%' height='100%' fill='white' />
<text x='{width / 2}' y='24' font-size='18' text-anchor='middle' font-family='Arial'>{title}</text>
<line x1='{padding}' y1='{height - padding}' x2='{width - padding}' y2='{height - padding}' stroke='#111827' />
<line x1='{padding}' y1='{padding}' x2='{padding}' y2='{height - padding}' stroke='#111827' />
<polyline fill='none' stroke='#1d4ed8' stroke-width='2' points='{points}' />
{circles}
<text x='{width / 2}' y='{height - 10}' font-size='12' text-anchor='middle' font-family='Arial'>{x_label}</text>
<text x='18' y='{height / 2}' font-size='12' text-anchor='middle' transform='rotate(-90 18 {height / 2})' font-family='Arial'>{y_label}</text>
</svg>"""
    path.write_text(svg)


def _select_scenario(case: ExperimentCase) -> dict:
    if case.scenario_source == "actual_ion_xml":
        return load_actual_ion_schedule(case.scenario_path)
    return generate_scenario(
        topology=case.topology,
        node_count=case.node_count,
        bandwidth_bps=case.bandwidth_bps,
        owlt=case.owlt,
        disruption=case.disruption,
        name=case.name,
    )


def _launch_process(cmd: List[str], *, cwd: str, log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w")
    return subprocess.Popen(cmd, cwd=cwd, stdout=log_handle, stderr=subprocess.STDOUT)


def _stop_process(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _receiver_script() -> str:
    return """
import json
from emion.core.engine import EmionEngine
node_id = int(__import__('sys').argv[1])
base_dir = __import__('sys').argv[2]
timeout_s = int(__import__('sys').argv[3])
try:
    engine = EmionEngine(node_id, base_dir=base_dir)
    engine.attach()
    data = engine.receive(f'ipn:{node_id}.1', timeout=timeout_s)
    if not data:
        print(json.dumps({'status': 'timeout', 'node_id': node_id}))
    else:
        print(json.dumps({'status': 'received', 'node_id': node_id, 'payload_hex': data.hex()}))
except Exception as exc:
    print(json.dumps({'status': 'error', 'node_id': node_id, 'error': str(exc)}))
"""


def _start_receiver(node_id: int, *, base_dir: str, timeout_s: int) -> subprocess.Popen:
    return subprocess.Popen(
        ["python3", "-u", "-c", _receiver_script(), str(node_id), base_dir, str(timeout_s)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _collect_receiver_result(proc: subprocess.Popen, *, node_id: int, timeout_s: int) -> dict:
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s + 10)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        return {"status": "timeout", "node_id": node_id, "stdout": stdout, "stderr": stderr}
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    payload = {}
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            payload = json.loads(line)
            break
    if payload.get("status") != "received":
        return payload or {"status": "timeout", "node_id": node_id, "stdout": stdout, "stderr": stderr}
    raw_bytes = bytes.fromhex(payload["payload_hex"])
    if not raw_bytes:
        return {"status": "timeout", "node_id": node_id}

    received_ts = time.time()
    trace_id, unwrapped = _extract_trace_id_and_payload(raw_bytes)
    return {
        "status": "received",
        "node_id": node_id,
        "trace_id": trace_id,
        "payload_size": len(unwrapped),
        "payload_text": unwrapped.decode("utf-8", errors="replace"),
        "received_ts": received_ts,
    }


def run_case(case: ExperimentCase, *, repo_root: Path, output_root: Path) -> dict:
    base_url = f"http://127.0.0.1:{case.dashboard_port}"
    ws_url = f"ws://127.0.0.1:{case.dashboard_port}/ws"
    case_dir = output_root / case.name
    case_dir.mkdir(parents=True, exist_ok=True)

    dashboard_proc = _launch_process(
        ["emion", "dashboard", "--host", "127.0.0.1", "--port", str(case.dashboard_port)],
        cwd=str(repo_root),
        log_path=case_dir / "dashboard.log",
    )
    ml_proc = None
    telemetry_rows: List[dict] = []
    resource_rows: List[dict] = []
    bundle_rows: List[dict] = []
    telemetry_stop = threading.Event()
    resource_stop = threading.Event()
    action_scheduler = None

    try:
        _wait_for_http(base_url)
        requests.post(f"{base_url}/api/reset", timeout=15)

        if case.attach_ml_module:
            detector_path = repo_root / "examples" / "anomaly_detector" / "ml_detector.py"
            ml_proc = _launch_process(
                ["python3", str(detector_path), "--port", "8421"],
                cwd=str(repo_root),
                log_path=case_dir / "ml_detector.log",
            )
            time.sleep(4)

        scenario = _select_scenario(case)
        (case_dir / "scenario.json").write_text(json.dumps(scenario, indent=2))

        for node_id in range(1, case.node_count + 1):
            requests.post(f"{base_url}/api/nodes", params={"node_id": node_id}, timeout=10)

        requests.post(f"{base_url}/api/scenario/load", json=scenario, timeout=15)

        if case.attach_ml_module:
            requests.post(
                f"{base_url}/api/nodes/1/modules",
                params={"url": "http://127.0.0.1:8421", "name": "MLDetector", "module_type": "anomaly"},
                timeout=10,
            )

        telemetry_listener = TelemetryListener(ws_url, telemetry_rows, telemetry_stop)
        resource_sampler = ResourceSampler(base_url, case.telemetry_sample_s, resource_rows, resource_stop)
        telemetry_listener.start()
        resource_sampler.start()

        requests.post(f"{base_url}/api/start", params={"startup_wait": case.startup_wait_s}, timeout=120)
        requests.post(f"{base_url}/api/scenario/start", timeout=15)

        runtime_actions = scenario.get("runtime_actions", [])
        if runtime_actions:
            action_scheduler = RuntimeActionScheduler(base_url, runtime_actions, case.startup_wait_s)
            action_scheduler.arm(time.time())
            action_scheduler.start()

        time.sleep(case.warmup_s)
        traffic_pairs = _traffic_pairs(case)
        pair_index = 0
        traffic_start_ts = time.time()

        for bundle_index in range(case.bundle_count):
            src_node, dst_node = traffic_pairs[pair_index % len(traffic_pairs)]
            pair_index += 1
            trace_id = f"{case.name}-b{bundle_index:04d}"
            payload = _make_payload(case.bundle_size, index=bundle_index)
            receiver_proc = _start_receiver(
                dst_node,
                base_dir=os.path.expanduser("~/ion_mars"),
                timeout_s=case.receive_timeout_s,
            )
            time.sleep(1)
            send_resp = requests.post(
                f"{base_url}/api/send",
                params={
                    "from_node": src_node,
                    "to_node": dst_node,
                    "payload": payload,
                    "trace_id": trace_id,
                },
                timeout=30,
            )
            send_payload = send_resp.json()
            recv_payload = _collect_receiver_result(
                receiver_proc,
                node_id=dst_node,
                timeout_s=case.receive_timeout_s,
            )
            if recv_payload.get("status") == "received":
                recv_payload["delivery_latency_ms"] = round(
                    (recv_payload["received_ts"] - float(send_payload.get("ts", time.time()))) * 1000.0,
                    3,
                )
            bundle_rows.append({
                "bundle_index": bundle_index,
                "trace_id": trace_id,
                "from_node": src_node,
                "to_node": dst_node,
                "payload_size": case.bundle_size,
                "send_size": send_payload.get("size", 0),
                "delivery_status": recv_payload.get("status", "error"),
                "delivery_latency_ms": recv_payload.get("delivery_latency_ms", 0.0),
                "hop_count": (send_payload.get("bundle_features") or {}).get("hop_count", 0),
                "queue_delay_ms": (send_payload.get("bundle_features") or {}).get("queue_delay_ms", 0.0),
                "contact_duration_s": (send_payload.get("bundle_features") or {}).get("contact_duration_s", 0.0),
                "module_inference_latency_ms": _mean([
                    result.get("inference_latency_ms", 0.0)
                    for result in (send_payload.get("modules") or {}).values()
                    if isinstance(result, dict)
                ]),
            })
            if case.bundle_interval_s:
                time.sleep(case.bundle_interval_s)

        traffic_end_ts = time.time()
        time.sleep(2)
        metrics_resp = requests.get(f"{base_url}/api/metrics", timeout=15)
        metrics = metrics_resp.json()

    finally:
        telemetry_stop.set()
        resource_stop.set()
        if action_scheduler:
            action_scheduler.stop()
        try:
            requests.post(f"{base_url}/api/reset", timeout=15)
        except requests.RequestException:
            pass
        _stop_process(ml_proc)
        _stop_process(dashboard_proc)

    _write_csv(case_dir / "bundle_metrics.csv", bundle_rows)
    _write_csv(case_dir / "resource_metrics.csv", resource_rows)
    _write_csv(case_dir / "telemetry_metrics.csv", telemetry_rows)
    (case_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    resource_cpu = [float(row["cpu_percent"]) for row in resource_rows if row.get("cpu_percent") is not None]
    resource_rss = [float(row["rss_bytes"]) for row in resource_rows if row.get("rss_bytes") is not None]
    telemetry_latency = [float(row["latency_ms"]) for row in telemetry_rows]
    delivered_rows = [row for row in bundle_rows if row.get("delivery_status") == "received"]
    delivery_latencies = [float(row["delivery_latency_ms"]) for row in delivered_rows if row.get("delivery_latency_ms")]
    throughput_bps = 0.0
    if traffic_end_ts > traffic_start_ts:
        throughput_bps = (
            sum(int(row["payload_size"]) for row in delivered_rows) * 8.0
        ) / (traffic_end_ts - traffic_start_ts)

    summary = {
        "experiment": case.name,
        "topology": case.topology,
        "node_count": case.node_count,
        "bundle_count": case.bundle_count,
        "bundle_size": case.bundle_size,
        "bundle_rate_per_s": round(1.0 / case.bundle_interval_s, 4) if case.bundle_interval_s else float(case.bundle_count),
        "delivery_ratio": round(len(delivered_rows) / len(bundle_rows), 4) if bundle_rows else 0.0,
        "avg_delivery_latency_ms": _mean(delivery_latencies),
        "avg_contact_creation_latency_ms": metrics["routing"]["control_plane"]["contact_creation_latency"]["avg_ms"],
        "routing_overhead_commands": metrics["routing"]["control_plane"]["ionadmin_dispatch_total"],
        "avg_dashboard_latency_ms": _mean(telemetry_latency),
        "avg_cpu_percent": _mean(resource_cpu),
        "avg_rss_mb": round((_mean(resource_rss) / (1024 * 1024)), 6) if resource_rss else 0.0,
        "throughput_bps": round(throughput_bps, 6),
        "avg_module_inference_latency_ms": metrics["modules"]["bundle_inference_latency_ms"]["avg"],
    }
    (case_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def run_matrix(*, config_path: Optional[str], output_dir: str, repo_root: str) -> Path:
    repo = Path(repo_root).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cases = _load_cases(config_path)
    summaries = [run_case(case, repo_root=repo, output_root=output_root) for case in cases]
    summary_csv = output_root / "summary.csv"
    _write_csv(summary_csv, summaries)

    by_nodes = sorted(
        ((float(item["node_count"]), float(item["delivery_ratio"])) for item in summaries if item["experiment"].startswith("scalability_")),
        key=lambda row: row[0],
    )
    by_cpu = sorted(
        ((float(item["node_count"]), float(item["avg_cpu_percent"])) for item in summaries if item["experiment"].startswith("scalability_")),
        key=lambda row: row[0],
    )
    by_memory = sorted(
        ((float(item["node_count"]), float(item["avg_rss_mb"])) for item in summaries if item["experiment"].startswith("scalability_")),
        key=lambda row: row[0],
    )
    by_rate = sorted(
        ((float(item["bundle_rate_per_s"]), float(item["avg_dashboard_latency_ms"])) for item in summaries if item["experiment"].startswith("dashboard_latency_")),
        key=lambda row: row[0],
    )
    by_size = sorted(
        ((float(item["bundle_size"]), float(item["throughput_bps"])) for item in summaries if item["experiment"].startswith("throughput_size_")),
        key=lambda row: row[0],
    )
    by_inference_rate = sorted(
        ((float(item["bundle_rate_per_s"]), float(item["avg_module_inference_latency_ms"])) for item in summaries if item["experiment"].startswith("ml_rate_")),
        key=lambda row: row[0],
    )

    _write_svg_line_chart(output_root / "delivery_ratio_vs_nodes.svg", title="Delivery ratio vs node count", x_label="Nodes", y_label="Delivery ratio", rows=by_nodes)
    _write_svg_line_chart(output_root / "cpu_vs_nodes.svg", title="CPU usage vs node count", x_label="Nodes", y_label="CPU percent", rows=by_cpu)
    _write_svg_line_chart(output_root / "memory_vs_nodes.svg", title="Memory usage vs node count", x_label="Nodes", y_label="RSS (MB)", rows=by_memory)
    _write_svg_line_chart(output_root / "dashboard_latency_vs_bundle_rate.svg", title="Dashboard latency vs bundle rate", x_label="Bundles per second", y_label="Latency (ms)", rows=by_rate)
    _write_svg_line_chart(output_root / "throughput_vs_bundle_size.svg", title="Throughput vs bundle size", x_label="Bundle size (bytes)", y_label="Throughput (bps)", rows=by_size)
    _write_svg_line_chart(output_root / "inference_latency_vs_bundle_rate.svg", title="Inference latency vs bundle rate", x_label="Bundles per second", y_label="Inference latency (ms)", rows=by_inference_rate)
    return summary_csv


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run automated EmION experiments")
    parser.add_argument("--config", default="", help="Path to a JSON experiment config")
    parser.add_argument("--output-dir", default="artifacts/experiments", help="Directory for CSV and SVG outputs")
    parser.add_argument("--repo-root", default=os.getcwd(), help="Repository root")
    args = parser.parse_args(argv)
    summary_csv = run_matrix(config_path=args.config or None, output_dir=args.output_dir, repo_root=args.repo_root)
    print(summary_csv)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

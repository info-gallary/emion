import pytest

from emion.dashboard import server
from emion.experiments.runner import _aggregate_replicates
from emion.experiments.scenarios import generate_scenario


def test_generate_line_scenario_has_positions_and_contacts():
    scenario = generate_scenario(topology="line", node_count=5)
    set_positions = [event for event in scenario["events"] if event["action"] == "set_position"]
    add_contacts = [event for event in scenario["events"] if event["action"] == "add_contact"]

    assert scenario["node_count"] == 5
    assert len(set_positions) == 5
    assert len(add_contacts) == 8  # four links, bidirectional


def test_generate_node_crash_scenario_exposes_runtime_actions():
    scenario = generate_scenario(topology="line", node_count=5, disruption="node_crash")
    action_types = [action["type"] for action in scenario["runtime_actions"]]

    assert "stop_node" in action_types
    assert "start_node" in action_types


def test_generate_leo_geo_scenario_scales_to_twenty_nodes():
    scenario = generate_scenario(topology="leo_geo", node_count=20)
    set_positions = [event for event in scenario["events"] if event["action"] == "set_position"]
    add_contacts = [event for event in scenario["events"] if event["action"] == "add_contact"]

    assert scenario["layout"] == "leo_geo"
    assert scenario["node_count"] == 20
    assert len(set_positions) == 20
    assert len(add_contacts) >= 40


def test_aggregate_replicates_adds_variability_columns():
    rows = [
        {
            "experiment": "case",
            "topology": "ring",
            "disruption": "none",
            "node_count": 5,
            "bundle_count": 2,
            "bundle_size": 128,
            "bundle_rate_per_s": 1.0,
            "delivery_ratio": 1.0,
            "avg_delivery_latency_ms": 10.0,
            "avg_cpu_percent": 1.0,
            "avg_rss_mb": 20.0,
            "throughput_bps": 100.0,
        },
        {
            "experiment": "case",
            "topology": "ring",
            "disruption": "none",
            "node_count": 5,
            "bundle_count": 2,
            "bundle_size": 128,
            "bundle_rate_per_s": 1.0,
            "delivery_ratio": 0.5,
            "avg_delivery_latency_ms": 20.0,
            "avg_cpu_percent": 2.0,
            "avg_rss_mb": 22.0,
            "throughput_bps": 80.0,
        },
    ]

    summary = _aggregate_replicates(rows)[0]

    assert summary["run_count"] == 2
    assert summary["delivery_ratio"] == 0.75
    assert "delivery_ratio_std" in summary
    assert "avg_delivery_latency_ms_ci95" in summary


def test_extract_trace_id_and_payload_roundtrip():
    trace_id, payload = server._extract_trace_id_and_payload(b"__EMION_TRACE__abc123\nhello")
    assert trace_id == "abc123"
    assert payload == b"hello"


def test_extract_bundle_features_uses_forecast_path():
    server.reset_dashboard_metrics()
    features = server.extract_bundle_features(
        1,
        3,
        b"payload",
        {
            "predicted_path": [1, 2, 3],
            "available_at": 4.0,
        },
        ttl_seconds=120,
        retransmission_count=2,
    )

    assert features["bundle_size"] == len(b"payload")
    assert features["hop_count"] == 2
    assert features["ttl_seconds"] == 120
    assert features["retransmission_count"] == 2
    assert features["route_length"] == 3

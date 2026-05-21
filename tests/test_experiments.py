import pytest

from emion.dashboard import server
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

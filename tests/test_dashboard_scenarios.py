import textwrap
import time

from fastapi.testclient import TestClient
import pytest

from emion.dashboard.server import create_app


pytestmark = [pytest.mark.dashboard]


def test_dashboard_accepts_custom_xml_scenario():
    xml_body = textwrap.dedent(
        """\
        <scenario name="Custom Relay" wlan_range="175" wlan_rate="900000">
          <nodes>
            <node id="1" x="100" y="120" wlan="true" />
            <node id="2" x="220" y="120" wlan="true" />
            <node id="3" x="360" y="120" />
          </nodes>
          <links>
            <link from="2" to="3" rate="750000" delay="4" />
          </links>
          <events>
            <event time="12" action="move_linear" node="1" from_x="100" from_y="120" to_x="180" to_y="180" duration="8" />
          </events>
        </scenario>
        """
    )

    client = TestClient(create_app())
    files = {"file": ("custom.xml", xml_body, "application/xml")}

    upload_resp = client.post("/api/scenario/upload-xml", files=files)
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert upload_data["status"] == "parsed"
    assert upload_data["name"] == "Custom Relay"
    assert upload_data["node_count"] == 3
    assert upload_data["link_count"] == 1
    assert upload_data["wlan_node_count"] == 2
    assert upload_data["briefing"]["node_ids"] == [1, 2, 3]

    scenario = upload_data["scenario"]
    load_resp = client.post("/api/scenario/load", json=scenario)
    assert load_resp.status_code == 200
    load_data = load_resp.json()
    assert load_data["status"] == "loaded"
    assert load_data["count"] == len(scenario["events"])
    assert load_data["scenario_telemetry"]["tracked_node_count"] == 3
    assert load_data["scenario_telemetry"]["wlan_link_count"] == 1
    assert load_data["scenario_telemetry"]["wired_link_count"] == 1

    start_resp = client.post("/api/scenario/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "started"

    time.sleep(0.8)
    status_resp = client.get("/api/scenario/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["name"] == "Custom Relay"
    assert status_data["is_running"] is True
    assert status_data["executed_events"] >= 7

    stop_resp = client.post("/api/scenario/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"

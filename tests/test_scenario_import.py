from pathlib import Path
from tempfile import TemporaryDirectory
import textwrap
import unittest
import pytest

from emion.core.mars_import import parse_core_xml_scenario
from emion.core.scenarios import ScenarioManager


REPO_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [pytest.mark.scenario]


class ScenarioImportTests(unittest.TestCase):
    def test_core_xml_import_preserves_mobility(self):
        scenario = parse_core_xml_scenario(REPO_ROOT / "examples" / "ion_mars" / "mars.xml", loop_count=1)

        move_events = [event for event in scenario["events"] if event["action"] == "move_linear"]
        self.assertGreater(len(move_events), 0)
        self.assertEqual(sorted(scenario["wlan_nodes"]), [2, 3, 4, 5, 6])
        self.assertGreaterEqual(scenario["wlan_rate"], 54000000)
        self.assertGreaterEqual(scenario["wlan_owlt"], 1)

    def test_core_xml_import_handles_custom_topologies(self):
        scenario = parse_core_xml_scenario(REPO_ROOT / "examples" / "complex_scenarios" / "hex_ring.xml")

        position_events = [event for event in scenario["events"] if event["action"] == "set_position"]
        self.assertEqual(len(position_events), 6)
        self.assertEqual(sorted(scenario["wlan_nodes"]), [1, 2, 3, 4, 5, 6])
        self.assertEqual(scenario["wlan_range"], 210.0)

    def test_custom_event_xml_is_supported(self):
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
        with TemporaryDirectory() as tmp_dir:
            xml_path = Path(tmp_dir) / "custom.xml"
            xml_path.write_text(xml_body)
            scenario = parse_core_xml_scenario(xml_path)

        self.assertEqual(scenario["name"], "Custom Relay")
        self.assertEqual(scenario["wlan_range"], 175.0)
        self.assertEqual(sorted(scenario["wlan_nodes"]), [1, 2])
        self.assertTrue(any(event["action"] == "move_linear" for event in scenario["events"]))
        self.assertTrue(any(event["action"] == "add_contact" for event in scenario["events"]))


class ScenarioForecastTests(unittest.TestCase):
    def test_future_path_uses_upcoming_contacts(self):
        manager = ScenarioManager()
        manager.load_scenario(
            {
                "name": "Forecast",
                "events": [
                    {"time": 0.0, "action": "set_position", "args": [1, 0, 0]},
                    {"time": 0.0, "action": "set_position", "args": [2, 10, 0]},
                    {"time": 0.0, "action": "set_position", "args": [3, 20, 0]},
                    {"time": 5.0, "action": "add_contact", "args": [1, 2, "+0", "+60", 500000, 1.0, 1]},
                    {"time": 5.0, "action": "add_contact", "args": [2, 3, "+0", "+60", 500000, 1.0, 1]},
                ],
            }
        )

        forecast = manager.get_future_path(1, 3)
        self.assertEqual(forecast["predicted_path"], [1, 2, 3])
        self.assertEqual(forecast["available_at"], 5.0)
        self.assertEqual(forecast["reason"], "future_scheduled_contact")


if __name__ == "__main__":
    unittest.main()

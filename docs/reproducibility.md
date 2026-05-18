# Reproducibility Guide

This guide is meant for reviewers, contributors, and paper readers who want a predictable way to validate EmION.

## Scope

EmION has two useful validation layers:

1. Fast software checks for scenario parsing, dashboard upload/load behavior, and route forecasting.
2. Full integration checks that boot real ION-DTN components and exercise bundle delivery.

## Prerequisites

- Linux or WSL2
- Python 3.8+
- The ION-DTN toolchain installed and available to EmION

For the dashboard and test extras:

```bash
pip install -e ".[dashboard,test]"
```

## Fast Validation

These checks finish quickly and are the best first pass for reviewers:

```bash
pytest -q tests/test_scenario_import.py tests/test_dashboard_scenarios.py
```

What this covers:

- Parsing CORE XML scenarios
- Parsing EmION custom scenario XML
- Dashboard upload and load flow for custom `.xml` files
- Scenario preview telemetry, node positions, and initial link rendering inputs
- Future route forecasting from scheduled contact events

## Full Integration Validation

This suite exercises the real ION-backed workflow and takes longer:

```bash
pytest -q tests/test_emion.py
```

What this covers:

- Two-node ION startup
- Bundle delivery between real nodes
- Dashboard startup
- Example anomaly detector integration

## Custom XML Scenario Smoke Test

The dashboard accepts custom scenario files with the following high-level structure:

```xml
<scenario name="Custom Relay" wlan_range="175" wlan_rate="900000">
  <nodes>
    <node id="1" x="100" y="120" wlan="true" />
    <node id="2" x="220" y="120" wlan="true" />
  </nodes>
  <links>
    <link from="1" to="2" rate="750000" delay="4" />
  </links>
  <events>
    <event time="12" action="move_linear" node="1"
           from_x="100" from_y="120" to_x="180" to_y="180" duration="8" />
  </events>
</scenario>
```

To validate visually:

1. Run `emion dashboard`
2. Open `http://localhost:8420`
3. Upload a custom `.xml` scenario in the Scenario Engine panel
4. Confirm the canvas shows nodes and initial links after load
5. Start the scenario and confirm movement and link updates progress over time

## Notes for Reviewers

- The fast tests are the best way to verify scenario and dashboard behavior without needing the full DTN runtime path.
- The integration suite is intentionally slower because it validates the real ION-backed workflow rather than a mocked transport.

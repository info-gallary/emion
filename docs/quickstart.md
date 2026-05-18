# Quickstart

This guide aims to get a new user from clone to a visible EmION workflow quickly.

## 1. Install

From the repository root:

```bash
pip install -e ".[dashboard,test]"
```

If you need the full local environment setup for ION-backed execution, run:

```bash
chmod +x install.sh && ./install.sh
```

## 2. Verify the Fast Checks

Before opening the dashboard, confirm the scenario and dashboard workflow layer works:

```bash
pytest -q tests/test_scenario_import.py tests/test_dashboard_scenarios.py
```

Expected result:

- all tests pass
- custom XML upload/load behavior is validated

## 3. Launch the Dashboard

```bash
emion dashboard
```

Then open:

```text
http://localhost:8420
```

## 4. Load a Scenario

In the dashboard:

1. Open the `SCENARIO ENGINE` panel
2. Upload a scenario XML file
3. Confirm the scenario briefing appears
4. Confirm nodes and links appear on the canvas

Good starting files:

- `examples/ion_mars/mars.xml`
- `examples/complex_scenarios/hex_ring.xml`

## 5. Start the Scenario

Click `Start` in the scenario controls.

Expected behavior:

- the progress state changes
- node motion begins for scenarios with mobility events
- link state updates appear in the canvas and telemetry

## 6. Optional: Run the Full Integration Test

If your environment includes the real ION runtime and supporting tools:

```bash
pytest -q tests/test_emion.py
```

## 7. Next Steps

- Read [architecture.md](architecture.md) for the system design
- Read [api.md](api.md) for backend endpoints
- Read [scenario_format.md](scenario_format.md) to author custom XML
- Read [troubleshooting.md](troubleshooting.md) if the environment behaves unexpectedly

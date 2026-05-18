# Troubleshooting

This page collects the most common issues when running EmION locally.

## The Dashboard Starts but the Canvas Looks Empty

Check the following:

- A scenario was actually loaded
- The uploaded XML produced `set_position` events or node definitions
- The browser developer console does not show JavaScript errors
- The backend is returning `node_positions` and `scenario_links`

Fast validation command:

```bash
pytest -q tests/test_scenario_import.py tests/test_dashboard_scenarios.py
```

## Custom XML Upload Fails

Common causes:

- malformed XML
- unsupported attribute names
- missing `id` values on nodes
- events missing required action-specific attributes

See [scenario_format.md](scenario_format.md) for the supported structure.

## `fastapi.testclient` or Dashboard Tests Fail Due to `httpx`

Install the test extras:

```bash
pip install -e ".[dashboard,test]"
```

## Dashboard Boots but Real Node Operations Fail

EmION relies on the real ION-DTN runtime. Make sure:

- the ION toolchain is installed
- commands such as `ionadmin` are on `PATH`
- your environment supports the required ION runtime behavior

Useful command:

```bash
emion info
```

## Full Test Suite Takes a Long Time

This is expected. The integration test intentionally boots real ION-backed components.

Use the quick validation path during iteration:

```bash
pytest -q tests/test_scenario_import.py tests/test_dashboard_scenarios.py
```

Run the full path when you want end-to-end confidence:

```bash
pytest -q tests/test_emion.py
```

## Running on Native Windows

Native Windows is not the intended target. Use:

- Linux
- WSL2
- Docker

## Port Conflict on `8420`

Launch the dashboard on another port:

```bash
emion dashboard --port 8520
```

## Uploaded Scenario Parses but Motion Does Not Appear

Check that:

- the scenario was started after being loaded
- `move_linear` events include `from_x`, `from_y`, `to_x`, `to_y`, and `duration`
- the event time is within the scenario window you are watching

## I Am Not Sure Whether a Problem Is in the Parser or the UI

Split the problem into layers:

1. Run the scenario tests
2. Inspect the upload response from `/api/scenario/upload-xml`
3. Inspect the load response from `/api/scenario/load`
4. Verify the scenario object contains positions and events

This usually makes it clear whether the issue is import, backend state, or frontend rendering.

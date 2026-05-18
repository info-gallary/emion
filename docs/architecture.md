# Architecture Overview

EmION combines a real ION-DTN runtime with a Python control layer and a browser dashboard.

## Main Components

### `emion.pyion`

This package exposes Python bindings for selected ION-DTN capabilities. It is the lowest-level EmION layer and is responsible for talking to the real ION runtime rather than a simulated transport.

Representative responsibilities:

- Bundle Protocol send and receive operations
- Management actions such as contact and range updates
- Access to supporting DTN primitives

### `emion.core`

This is the orchestration layer around the bindings.

- [engine.py](../emion/core/engine.py) manages per-node runtime interaction
- [node.py](../emion/core/node.py) manages node directories, startup, shutdown, and peer configuration
- [scenarios.py](../emion/core/scenarios.py) executes scenario events over time
- [mars_import.py](../emion/core/mars_import.py) imports CORE XML and EmION custom XML scenarios

### `emion.dashboard`

This is the user-facing web application.

- [server.py](../emion/dashboard/server.py) exposes the FastAPI backend
- [static/app.js](../emion/dashboard/static/app.js) implements dashboard behavior and canvas rendering
- [static/index.html](../emion/dashboard/static/index.html) defines the dashboard UI

### `examples/`

The examples directory provides runnable reference material for common workflows:

- `ion_mars/` for XML-driven scenario import
- `anomaly_detector/` for module integration
- `complex_scenarios/` for additional topology examples

## Runtime Data Flow

### 1. Node Lifecycle

1. The dashboard or CLI requests node creation.
2. `EmionNode` prepares the node workspace and peer relationships.
3. `EmionEngine` attaches to running nodes once ION is booted.

### 2. Scenario Execution

1. A `.xml` scenario is uploaded or loaded.
2. `parse_core_xml_scenario()` converts XML into EmION’s internal event structure.
3. `ScenarioManager.load_scenario()` seeds preview state such as node positions and initial links.
4. `ScenarioManager.start()` replays timed contact, range, and mobility events.
5. The dashboard receives updated telemetry and renders the evolving topology.

### 3. Bundle Dispatch

1. The dashboard calls `/api/send`.
2. The backend resolves the source engine and sends a real BP bundle.
3. Attached per-node modules inspect payloads and may annotate behavior or routing advice.
4. The dashboard receives a websocket update and reflects the transmission visually.

## Scenario Model

A scenario is normalized into a JSON-like structure with:

- `name`
- `wlan_nodes`
- `wlan_range`
- `wlan_rate`
- `wlan_owlt`
- `events`

Event types currently used in the system include:

- `set_position`
- `move_linear`
- `add_contact`
- `delete_contact`
- `add_range`
- `delete_range`

## Why the Architecture Matters

EmION is not just a front-end animation layer. The dashboard is a visualization and control surface over a real ION-DTN-backed runtime. That is the main architectural distinction from purely synthetic DTN visualizers.

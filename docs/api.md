# Dashboard API Reference

This document summarizes the HTTP endpoints exposed by the EmION dashboard backend in [server.py](../emion/dashboard/server.py).

## Base URL

By default:

```text
http://localhost:8420
```

## Scenario Endpoints

### `GET /api/scenario/list`

Returns known scenario definitions from the runtime scenario directory.

### `POST /api/scenario/upload-xml`

Uploads and parses a scenario XML file.

Form field:

- `file`: `.xml` file upload

Typical response fields:

- `status`
- `id`
- `name`
- `events`
- `node_count`
- `link_count`
- `wlan_node_count`
- `briefing`
- `scenario`

### `POST /api/scenario/load`

Loads a parsed scenario into the active scenario manager.

Request body:

- scenario object with `events` and optional WLAN metadata

Typical response fields:

- `status`
- `count`
- `briefing`
- `scenario_links`
- `node_positions`
- `scenario_telemetry`

### `POST /api/scenario/start`

Starts timed scenario execution.

### `POST /api/scenario/stop`

Stops timed scenario execution.

### `GET /api/scenario/status`

Returns current scenario progress information such as:

- name
- running status
- elapsed time
- executed and pending event counts

## Node and Network Endpoints

### `POST /api/nodes?node_id=<id>`

Registers a node with the dashboard backend.

### `GET /api/nodes`

Returns current registered node state.

### `POST /api/start`

Boots all registered nodes and attaches engines.

### `POST /api/stop`

Stops all running nodes.

### `POST /api/reset`

Clears node, engine, module, and scenario state.

### `GET /api/links`

Returns current active links. When a scenario is running, the result reflects scenario-managed links.

## Bundle and File Transfer Endpoints

### `POST /api/send?from_node=<id>&to_node=<id>&payload=<text>`

Sends a bundle between two nodes.

Typical response fields:

- source and destination EIDs
- payload size
- module analysis results
- route plan metadata

### `POST /api/cfdp/send?from_node=<id>&to_node=<id>&file=<path>`

Initiates a CFDP file transfer.

## Module Endpoints

The dashboard backend also exposes endpoints for attaching per-node modules. The exact payload handling lives in the backend module-management section of [server.py](../emion/dashboard/server.py).

Expected external module contract:

- `GET /health`
- `POST /analyze`

See [../examples/anomaly_detector/README.md](../examples/anomaly_detector/README.md) for a concrete example.

## WebSocket Updates

The dashboard also uses websocket pushes for live events such as:

- network start and stop
- scenario load and start
- bundle sends
- telemetry updates

For most users, the JavaScript client in [../emion/dashboard/static/app.js](../emion/dashboard/static/app.js) is the clearest reference for the live event stream.

# Custom XML Scenario Format

EmION supports two broad XML inputs:

1. CORE-style scenario XML
2. EmION custom scenario XML

This page documents the EmION custom format intended for direct authoring.

## Top-Level Structure

```xml
<scenario name="Custom Relay" wlan_range="175" wlan_rate="900000" wlan_owlt="1">
  <nodes>...</nodes>
  <links>...</links>
  <events>...</events>
</scenario>
```

Supported top-level attributes:

- `name`
- `wlan_range`
- `wlan_rate`
- `wlan_owlt`

## Nodes

Nodes establish the initial topology and optional WLAN membership.

Example:

```xml
<nodes>
  <node id="1" x="100" y="120" wlan="true" />
  <node id="2" x="220" y="120" wlan="true" />
  <node id="3" x="360" y="120" />
</nodes>
```

Supported node attributes:

- `id`
- `x`
- `y`
- `from_x`
- `from_y`
- `wlan`

Notes:

- `x` and `y` define initial positions
- `wlan="true"` marks a node as part of the WLAN visibility set

## WLAN Membership Block

WLAN membership can also be expressed explicitly:

```xml
<wlan>
  <member node="1" />
  <member node="2" />
</wlan>
```

## Links

Links define scheduled point-to-point relationships or WLAN grouping hints.

Example:

```xml
<links>
  <link from="2" to="3" rate="750000" delay="4" />
</links>
```

Supported link attributes:

- `from` or `node1`
- `to` or `node2`
- `kind`
- `rate` or `bandwidth`
- `delay` or `owlt`
- `confidence`
- `start`
- `end`
- `unidirectional`

Behavior:

- default `kind` is `scheduled`
- scheduled links are expanded into contact and range events
- `kind="wlan"` adds nodes to the WLAN set instead of generating scheduled contacts

## Events

The event block defines time-based behavior.

```xml
<events>
  <event time="12" action="move_linear" node="1"
         from_x="100" from_y="120" to_x="180" to_y="180" duration="8" />
</events>
```

Supported actions:

### `set_position`

```xml
<event time="0" action="set_position" node="1" x="100" y="120" />
```

### `move_linear`

```xml
<event time="12" action="move_linear" node="1"
       from_x="100" from_y="120" to_x="180" to_y="180" duration="8" />
```

### `add_contact`

```xml
<event time="0" action="add_contact" from="1" to="3"
       start="+0" end="+4000000" rate="600000" confidence="1.0" />
```

### `delete_contact`

```xml
<event time="15" action="delete_contact" from="1" to="3" start="+0" />
```

### `add_range`

```xml
<event time="0" action="add_range" from="1" to="3"
       start="+0" end="+4000000" delay="2" />
```

### `delete_range`

```xml
<event time="15" action="delete_range" from="1" to="3" start="+0" />
```

## Minimal Complete Example

```xml
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
    <event time="12" action="move_linear" node="1"
           from_x="100" from_y="120" to_x="180" to_y="180" duration="8" />
  </events>
</scenario>
```

## Practical Advice

- Prefer explicit `set_position`-style initial placement through node coordinates
- Use `<links>` for baseline scheduled connectivity
- Use `<events>` for topology changes and motion
- Test new custom scenarios first with:

```bash
pytest -q tests/test_scenario_import.py tests/test_dashboard_scenarios.py
```

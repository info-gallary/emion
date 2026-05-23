# Reproducibility Guide

This guide is meant for reviewers, contributors, and paper readers who want a predictable way to validate EmION.

## Scope

EmION has two useful validation layers:

1. Fast software checks for scenario parsing, dashboard upload/load behavior, and route forecasting.
2. Full integration checks that boot real ION-DTN components and exercise bundle delivery.
3. Automated experiment batches that export CSV and SVG artifacts.

## Prerequisites

- Linux or WSL2
- Python 3.8+
- The ION-DTN toolchain installed and available to EmION

For the dashboard and test extras:

```bash
pip install -e ".[dashboard,test]"
```

For experiment automation and the ML detector:

```bash
pip install -e ".[dashboard,test,experiments,ml]"
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

## Automated Experiment Matrix

Run the supplied experiment matrix:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/scalability_matrix.json \
  --output-dir artifacts/experiments_matrix
```

Additional configs:

- `examples/experiments/ml_matrix.json`
- `examples/experiments/robustness_matrix.json`
- `examples/experiments/mars_actual_schedule.json`
- `examples/experiments/baseline_one_comparison.json`

Exported artifacts:

- `summary.csv`
- `replicate_summary.csv` when any case uses `repeat_count > 1`
- per-case `bundle_metrics.csv`
- per-case `resource_metrics.csv`
- per-case `telemetry_metrics.csv`
- SVG plots for delivery ratio, CPU, memory, dashboard latency, throughput, and inference latency

Each matrix case may set `repeat_count` to run independent repetitions. The
top-level `summary.csv` then reports the mean value plus standard deviation and
95% confidence interval columns for delivery ratio, CPU, RSS, dashboard latency,
throughput, and disruption metrics. The raw per-run rows are preserved in
`replicate_summary.csv`.

## Reviewer-Oriented Experiment Batches

The default scalability matrix now includes star topologies at 3, 5, and 7
nodes plus a LEO/GEO-style constellation at 12, 16, and 20 nodes. The
constellation generator places LEO nodes in an orbital ring and GEO relay nodes
on an outer backbone with scheduled cross-links, so the 20-node case exercises a
larger multi-hop contact plan than the original small star scenarios.

For robustness, run:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/robustness_matrix.json \
  --output-dir artifacts/experiments_robustness
```

The robustness summary includes quantitative columns for
`pre_disruption_delivery_ratio`, `post_disruption_delivery_ratio`,
`delivery_degradation`, `rerouting_delay_ms`, and `recovery_time_s` for:

- node crash
- sudden contact failure
- intermittent connectivity
- bandwidth degradation

For a ONE-style baseline comparison, run:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/baseline_one_comparison.json \
  --output-dir artifacts/experiments_baseline_one
```

This configuration mirrors common ONE benchmarking dimensions: delivery
probability/ratio and latency are the primary routing metrics, and the reference
ONE literature uses Bluetooth-like 0.2 Mbps links, 10-70 nodes, and message
generation intervals of 1-3 minutes. Use the resulting EmION `delivery_ratio`,
`avg_delivery_latency_ms`, `throughput_bps`, and `routing_overhead_commands`
columns alongside the selected ONE paper values in the manuscript. Cite the ONE
simulator paper for the simulator feature set and metrics, and the MDPI
quantitative routing evaluation for the reference scenario dimensions:

- Keranen, Ott, and Karkkainen, "The ONE Simulator for DTN Protocol Evaluation",
  SIMUTools 2009.
- Massri et al., "Routing Protocols for Delay Tolerant Networks: A Reference
  Architecture and a Thorough Quantitative Evaluation", Computers 2016.

## Containerized Reproduction

Start the dashboard:

```bash
docker compose up dashboard
```

Run the sample experiment batch in a container:

```bash
docker compose run --rm --profile experiments runner
```

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

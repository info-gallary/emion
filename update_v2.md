# EmION Paper Update V2

This document summarizes the updates made in response to the latest reviewer comments.

## 1. Larger Scalability Evaluation

Reviewer concern: the previous scalability study used only 3-7 nodes, which was too small for broader DTN/space-network scenarios.

Updates made:

- Added a new `leo_geo` experiment topology in `emion/experiments/scenarios.py`.
- The topology models a LEO/GEO-style constellation:
  - LEO nodes are arranged in an orbital ring.
  - GEO relay nodes are placed on an outer relay backbone.
  - Scheduled cross-links connect LEO nodes to GEO relays.
- Expanded `examples/experiments/scalability_matrix.json` to include:
  - 3-node star
  - 5-node star
  - 7-node star
  - 12-node LEO/GEO constellation
  - 16-node LEO/GEO constellation
  - 20-node LEO/GEO constellation

The 20-node case directly addresses the reviewer request for a larger constellation-scale experiment.

## 2. Added Actual Graphs/Figures

Reviewer concern: the paper included tables but lacked actual graphs.

Updates made:

- The experiment runner already supported SVG generation, and the updated experiment flow now produces the requested plots.
- Generated preview graph artifacts are available in:

```text
artifacts/experiments_matrix_preview_combined/
```

Generated graphs:

- `delivery_ratio_vs_nodes.svg`
- `cpu_vs_nodes.svg`
- `memory_vs_nodes.svg`
- `dashboard_latency_vs_bundle_rate.svg`
- `throughput_vs_bundle_size.svg`

The combined preview summary is available at:

```text
artifacts/experiments_matrix_preview_combined/summary.csv
```

Note: the generated graphs are one-run preview graphs. The full reviewer-grade matrix uses 5 repeated runs per case and can be regenerated with:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/scalability_matrix.json \
  --output-dir artifacts/experiments_matrix
```

## 3. Robustness Evaluation Expanded

Reviewer concern: the robustness evaluation was incomplete and lacked quantitative experiments.

Updates made:

- Expanded `examples/experiments/robustness_matrix.json`.
- Added 5 repeated runs for each robustness case.
- Updated robustness cases to exercise:
  - node crash
  - sudden contact failure
  - intermittent connectivity
  - bandwidth degradation

New quantitative robustness metrics are now exported by `emion/experiments/runner.py`:

- `pre_disruption_delivery_ratio`
- `post_disruption_delivery_ratio`
- `delivery_degradation`
- `rerouting_delay_ms`
- `recovery_time_s`

Run command:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/robustness_matrix.json \
  --output-dir artifacts/experiments_robustness
```

## 4. Baseline Comparison Support

Reviewer concern: baseline comparison with ONE or DTNSim needed improvement.

Updates made:

- Added a new baseline comparison config:

```text
examples/experiments/baseline_one_comparison.json
```

- The config provides ONE-style comparison scenarios using:
  - 10-node ring topology
  - 20-node LEO/GEO topology
  - 0.2 Mbps link rate
  - 1 KB payloads
  - repeated runs

The comparison can report EmION values for:

- delivery ratio
- average delivery latency
- throughput
- routing overhead commands
- deployment/runtime behavior

Run command:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/baseline_one_comparison.json \
  --output-dir artifacts/experiments_baseline_one
```

Suggested papers for manuscript comparison:

- Keranen, Ott, and Karkkainen, "The ONE Simulator for DTN Protocol Evaluation", SIMUTools 2009.
- Massri et al., "Routing Protocols for Delay Tolerant Networks: A Reference Architecture and a Thorough Quantitative Evaluation", Computers 2016.

## 5. Multiple Runs and Statistical Reporting

Reviewer concern: experiments were single-run deterministic results.

Updates made:

- Added `repeat_count` support to `ExperimentCase` in `emion/experiments/runner.py`.
- Updated scalability and robustness matrices to use a minimum of 5 runs.
- The runner now writes:
  - aggregated `summary.csv`
  - raw per-run `replicate_summary.csv` when repeated runs are used

For repeated runs, the summary now includes:

- mean value
- standard deviation columns with `_std`
- 95% confidence interval columns with `_ci95`

This applies to key metrics such as delivery ratio, CPU, memory, latency, throughput, and robustness measurements.

## 6. Non-Perfect Results and More Stressful Scenarios

Reviewer concern: several earlier results were perfectly 1.0, such as delivery ratio and ML precision/recall.

Updates made:

- Added disruption-driven robustness cases that can produce degraded post-disruption delivery.
- Added larger LEO/GEO scenarios where startup, contact dispatch, and routing overhead increase with node count.
- Added measurement fields that separate pre-disruption and post-disruption behavior so imperfect recovery and degradation can be reported quantitatively.

Recommended next run for non-perfect delivery results:

```bash
python3 scripts/run_experiments.py \
  --config examples/experiments/robustness_matrix.json \
  --output-dir artifacts/experiments_robustness
```

## 7. Runner Reliability Updates

During graph generation, the 20-node LEO/GEO case exposed timeout limits in the experiment runner.

Updates made:

- Increased `/api/start` timeout based on node count.
- Increased `/api/scenario/start` timeout based on node count.
- This allows larger constellation scenarios to complete startup and contact-plan dispatch.

## 8. Tests Added

Updated `tests/test_experiments.py` with coverage for:

- 20-node `leo_geo` scenario generation.
- replicate aggregation with variability columns.

Verification command used:

```bash
pytest -q tests/test_experiments.py
```

Result:

```text
6 passed
```


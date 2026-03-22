# ION Mars Scenario

This example demonstrates a multi-node WLAN mobility scenario derived from the **CORE network emulator**.

## Files

| File | Description |
|------|-------------|
| `mars.xml` | CORE GUI scenario XML (5 WLAN nodes + 1 wired) |
| `mars.scen` | NS-2 mobility script embedded in the XML |
| `rcgen.sh` | Generates ION `.ionrc` config files for each node |
| `ion_start.sh` | Starts all ION nodes from generated configs |
| `build_mars.py` | Python script to parse `mars.xml` into EmION JSON |
| `run_ion_mars_core.sh` | Full walkthrough: start CORE → ION → EmION |

## Quick Start

```bash
# 1. Parse the XML scenario into EmION format
python build_mars.py

# 2. Or simply upload mars.xml via the EmION dashboard
#    (Scenario Engine → Drop .xml → it auto-parses)
```

## Using with EmION Dashboard

1. Start the dashboard: `emion dashboard`
2. Open `http://localhost:8420`
3. In **Scenario Engine**, click **Browse Files** and select `mars.xml`
4. The dashboard will parse the XML and show a **Scenario Briefing** in the telemetry panel
5. Click **▶ Start** to begin the simulation

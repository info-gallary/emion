# Examples & GUI

Emion comes with built-in verification tools and a simulation GUI.

## Health Check
The health check script verifies that the Python extension can load and access all required C symbols (`ion_attach`, `rfx_insert_contact`, etc.).

**Usage:**
```bash
python3 examples/health_check.py
```

## Simulation GUI
A PyQt5-based GUI allows you to visualize a 4-node network and interact with it.

**Location**: `examples/gui_sim.py`
**Dependencies**: `PyQt5`

**Usage:**
```bash
python3 examples/gui_sim.py
```

### Features

#### 1. Topology Visualization
The simulation window displays 4 nodes (1, 2, 3, 4) arranged simply. Connections between them are purely visual unless contacts are established.

#### 2. Attach/Detach
Click **"Attach ION"** to connect to the local ION-DTN instance. This calls `ion_attach()` and `bp_attach()`. 
> **Note**: This requires ION to be running on your machine (e.g., via `ionstart`). If ION is not running, the GUI logs an error but continues to function as a visualizer.

#### 3. Contact Management
Use the **Contact Graph Routing** panel to add contacts:
- Select **From Node** and **To Node**.
- Set **Rate** (bytes/sec).
- Click **Add Contact**.
- This calls `add_contact` (adding a contact record) and `add_range` (asserting visibility).

#### 4. Bundle Transmission
Use the **Bundle Protocol** panel to send data:
- Select **Source** EID (e.g., `ipn:1.1`).
- Select **Dest** EID (e.g., `ipn:2.1`).
- Click **Send Bundle**.
- This invokes `bp_send` to create a Bundle Protocol Data Unit (bundle) and pass it to the ION BP agent.

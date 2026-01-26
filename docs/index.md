# Welcome to emion

**emion** ("Embedded ION") is a Python wrapper for the [NASA/JPL ION-DTN](https://github.com/nasa-jpl/ION-DTN) implementation. It provides high-level Python bindings for Interplanetary Internet simulations and operations.

## Features

- **Native Bindings**: Direct C-level access to ION libraries (`libici`, `libbp`, `libcgr`).
- **High-Level API**: Pythonic `Node` class for easy management of DTN nodes.
- **Simulation Support**: Tools to manipulate the Contact Graph Routing (CGR) dynamically (add/remove contacts and ranges).
- **Visualization**: Includes a PyQt5-based simulation GUI.

## Installation

### Prerequisites
- **ION-DTN**: A working installation (or build) of ION-DTN.
- **Python 3.10+**

### Install from Source
```bash
git clone <repo-url>
cd emion
pip install .
```

To install with GUI dependencies:
```bash
pip install . PyQt5
```

## Quick Start
```python
from emion import Node

# Attach to the local ION node and send a bundle
with Node() as node:
    # Configure accessibility (Node 1 -> Node 2)
    node.add_contact(region=1, from_time=0, to_time=3600, 
                     from_node=1, to_node=2, rate=125000)
                     
    # Send data
    node.send(source_eid="ipn:1.1", dest_eid="ipn:2.1", 
              payload=b"Hello Mars/Earth!")
```

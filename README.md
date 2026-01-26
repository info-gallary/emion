# emion

**emion** ("Embedded ION") is a custom Python wrapper for the [ION-DTN](https://sourceforge.net/projects/ion-dtn/) implementation. It provides a high-level Python API for Interplanetary Overlay Network (ION) operations, including Bundle Protocol (BP) communication and Contact Graph Routing (CGR) management.

## Features

- **Python Bindings for ION**: Direct C integration for high performance.
- **Bundle Protocol**: Send and receive bundles using ION's BP stack.
- **Contact Graph Routing**: dynamic management of contacts and ranges.
- **Easy-to-use API**: Object-oriented wrappers (`Node`, `Endpoint`) for simplified interaction.

## Installation

### Prerequisites

- A working installation of ION-DTN (headers and libraries).
- Python 3.7+.
- C compiler (GCC/Clang).

### Install from Source

```bash
pip install .
```

To install in editable mode for development:

```bash
pip install -e ".[dev]"
```

## Usage

### Basic Setup

```python
import emion

# Check version
print(f"emion version: {emion.__version__}")
```

### Node Management

The `Node` class manages the attachment to the ION shared memory infrastructure.

```python
from emion import Node

with Node() as node:
    print("Attached to ION node!")
    # Operations here...
```

### Sending and Receiving Bundles

Use `Endpoint` to manage BP endpoints.

```python
from emion import Node, Endpoint

RECEIVER_EID = "ipn:1.1"
SENDER_EID = "ipn:1.2"

with Node() as node:
    # Create an endpoint for receiving
    # Note: Requires 'ipn:1.1' to be configured in ION
    try:
        with node.create_endpoint(RECEIVER_EID) as ep:
            # Receive with timeout (seconds)
            bundle = ep.receive(timeout=5)
            if bundle:
                src, payload = bundle
                print(f"Received from {src}: {payload}")
            else:
                print("No bundle received.")
                
            # Send a bundle
            ep.send("ipn:2.1", b"Hello from emion!")
            
    except RuntimeError as e:
        print(f"Error: {e}")
```

### Contact Graph Management

Dynamically update the contact plan.

```python
with Node() as node:
    # Add a contact
    # region, from_time, to_time, from_node, to_node, rate, confidence
    node.add_contact(1, 0, 100000, 1, 2, 100000)
    
    # Add a range
    # from_time, to_time, from_node, to_node, owlt
    node.add_range(0, 100000, 1, 2, 1)
```

## structure

- `src/emion/_core.c`: C extension module linking against ION.
- `src/emion/node.py`: High-level Python interface.
- `scripts/`: Helper scripts for ION runtime configuration.
- `examples/`: Verification scripts.

## License

MIT License.

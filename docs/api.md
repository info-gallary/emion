# API Reference

## Node Class
The `Node` class provides a high-level Pythonic interface to ION-DTN. It is the recommended way to interact with the system.

::: emion.Node
    options:
      members:
        - attach
        - detach
        - send
        - add_contact
        - remove_contact
        - add_range
        - remove_range
        - __enter__
        - __exit__

## Core Functions
Low-level bindings to the C extension. These are exposed via the `emion` module but are typically used internally by `Node`.

::: emion
    options:
      members:
        - ion_attach
        - ion_detach
        - bp_attach
        - bp_detach
        - bp_send
        - add_contact
        - remove_contact
        - add_range
        - remove_range

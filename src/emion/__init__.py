"""
emion: A custom Python module for ION-DTN.
"""

from .node import Node, Endpoint

__version__ = "0.0.1"

try:
    from ._core import (
        version as c_version,
        ion_attach,
        ion_detach,
        bp_attach,
        bp_detach,
        bp_open,
        bp_close,
        bp_receive,
        bp_send,
        add_contact,
        remove_contact,
        add_range,
        remove_range
    )
except ImportError:
    def c_version():
        return "C extension not loaded"
    
    def ion_attach(): pass
    def ion_detach(): pass
    def bp_attach(): pass
    def bp_detach(): pass
    def bp_send(source, dest, payload): pass
    def add_contact(region, from_time, to_time, from_node, to_node, rate, confidence): pass
    def remove_contact(region, from_time, from_node, to_node): pass
    def add_range(from_time, to_time, from_node, to_node, owlt): pass
    def remove_range(from_time, from_node, to_node): pass


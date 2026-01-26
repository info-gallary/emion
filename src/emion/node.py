try:
    from ._core import (
        ion_attach, ion_detach, bp_attach, bp_detach, 
        bp_open, bp_close, bp_receive, bp_send,
        add_contact, remove_contact, add_range, remove_range
    )
except ImportError:
    # Mock for doc generation or if extension missing
    def ion_attach(): pass
    def ion_detach(): pass
    def bp_attach(): pass
    def bp_detach(): pass
    def bp_open(eid): return object()
    def bp_close(sap): pass
    def bp_receive(sap, timeout): return None
    def bp_send(source, dest, payload): pass
    def add_contact(region, from_time, to_time, from_node, to_node, rate, confidence): pass
    def remove_contact(region, from_time, from_node, to_node): pass
    def add_range(from_time, to_time, from_node, to_node, owlt): pass
    def remove_range(from_time, from_node, to_node): pass

class Endpoint:
    """
    Represents a Bundle Protocol Endpoint (SAP).
    Used for sending and receiving bundles.
    """
    def __init__(self, eid: str):
        self.eid = eid
        self._sap = bp_open(eid)
    
    def receive(self, timeout: int = 0):
        """
        Receive a bundle.
        Returns (source_eid, payload) or None if timed out.
        """
        if self._sap is None:
             raise RuntimeError("Endpoint closed")
        return bp_receive(self._sap, timeout)
        
    def send(self, dest_eid: str, payload: bytes):
        """
        Send a bundle from this endpoint.
        """
        if self._sap is None:
             raise RuntimeError("Endpoint closed")
        return bp_send(self._sap, dest_eid, payload)
        
    def close(self):
        if self._sap:
            bp_close(self._sap)
            self._sap = None
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class Node:
    """
    High-level wrapper for an ION node.
    Manages attachment to shared memory and basic configuration.
    """
    def __init__(self):
        self._attached_ion = False
        self._attached_bp = False

    def attach(self):
        """Attach to ION and BP."""
        if not self._attached_ion:
            ion_attach()
            self._attached_ion = True
        
        if not self._attached_bp:
            bp_attach()
            self._attached_bp = True

    def detach(self):
        """Detach from ION and BP."""
        if self._attached_bp:
            bp_detach()
            self._attached_bp = False
            
        if self._attached_ion:
            ion_detach()
            self._attached_ion = False

    def create_endpoint(self, eid: str) -> Endpoint:
        """Create a new endpoint for receiving/sending."""
        if not self._attached_bp:
            raise RuntimeError("Node not attached to BP. Call attach() first.")
        return Endpoint(eid)

    def send(self, source_eid: str, dest_eid: str, payload: bytes):
        """Send a bundle (one-shot)."""
        if not self._attached_bp:
            raise RuntimeError("Node not attached to BP. Call attach() first.")
        
        return bp_send(source_eid, dest_eid, payload)

    def add_contact(self, region: int, from_time: int, to_time: int, from_node: int, to_node: int, rate: int, confidence: float = 1.0):
        """Add a contact to the contact graph."""
        if not self._attached_ion:
             raise RuntimeError("Node not attached to ION. Call attach() first.")
        add_contact(region, from_time, to_time, from_node, to_node, rate, confidence)

    def remove_contact(self, region: int, from_time: int, from_node: int, to_node: int):
        """Remove a contact from the contact graph."""
        if not self._attached_ion:
             raise RuntimeError("Node not attached to ION. Call attach() first.")
        remove_contact(region, from_time, from_node, to_node)

    def add_range(self, from_time: int, to_time: int, from_node: int, to_node: int, owlt: int):
        """Add a range to the contact graph."""
        if not self._attached_ion:
             raise RuntimeError("Node not attached to ION. Call attach() first.")
        add_range(from_time, to_time, from_node, to_node, owlt)

    def remove_range(self, from_time: int, from_node: int, to_node: int):
        """Remove a range from the contact graph."""
        if not self._attached_ion:
             raise RuntimeError("Node not attached to ION. Call attach() first.")
        remove_range(from_time, from_node, to_node)

    def __enter__(self):
        self.attach()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.detach()

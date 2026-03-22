"""
EmionEngine — Python interface to ION-DTN via pyion C-bindings.
Handles memory attachment, bundle send/receive.
No dummies — requires a running ION node.
"""

import os
import time
import pyion


class EmionEngine:
    """
    High-level Python wrapper over pyion C-bindings for a single ION node.
    Must be used after EmionNode.start() has booted the C daemons.
    """

    def __init__(self, node_id: int, base_dir: str = "/tmp/emion_nodes"):
        self.node_id = node_id
        self.node_dir = os.path.join(base_dir, str(node_id))
        self.proxy = None

    def attach(self, retries=5, delay=2):
        """Attach to the ION shared-memory region via pyion."""
        print(f"[EmION] Attaching engine to Node {self.node_id}...")

        # Ensure ION_NODE_LIST_DIR is unset — we use cwd instead
        os.environ.pop("ION_NODE_LIST_DIR", None)
        pyion.ION_NODE_LIST_DIR = None
        os.environ["ION_NODE_NUMBER"] = str(self.node_id)

        saved_dir = os.getcwd()
        os.chdir(self.node_dir)

        try:
            for attempt in range(1, retries + 1):
                try:
                    self.proxy = pyion.get_bp_proxy(self.node_id)
                    print(f"      ✅ Attached (attempt {attempt})")
                    return True
                except Exception as e:
                    print(f"      [!] Attempt {attempt}/{retries}: {e}")
                    time.sleep(delay)
        finally:
            os.chdir(saved_dir)

        raise RuntimeError(
            f"Cannot attach to ION Node {self.node_id}. "
            f"Is the node running? Check {self.node_dir}/node_boot.log"
        )

    def send(self, src_eid: str, dst_eid: str, payload: bytes):
        """Send a bundle via the real ION Bundle Protocol engine."""
        if not self.proxy:
            self.attach()
        with self.proxy.bp_open(src_eid) as ep:
            result = ep.bp_send(dst_eid, payload)
            print(f"      📡 Sent {len(payload)}B  {src_eid} → {dst_eid}")
            return result

    def receive(self, eid: str, timeout: int = 10):
        """Receive a bundle from the ION BP engine."""
        if not self.proxy:
            self.attach()
        with self.proxy.bp_open(eid) as ep:
            data = ep.bp_receive(timeout=timeout)
            if data:
                print(f"      📥 Received {len(data)}B on {eid}")
            return data

    def send_file(self, dst_node: int, source_path: str, dest_path: str = None):
        """Send a file via CFDP (interstellar file delivery)."""
        if not self.proxy:
            self.attach()
        
        print(f"[EmION] CFDP: Sending {source_path} to N{dst_node}...")
        cfdp_proxy = pyion.get_cfdp_proxy(self.node_id)
        
        # CFDP runs on top of a BP endpoint
        eid = f"ipn:{self.node_id}.64" # Standard ION CFDP endpoint
        with self.proxy.bp_open(eid) as ept:
            with cfdp_proxy.cfdp_open(dst_node, ept) as entity:
                entity.cfdp_send(source_path, dest_path or os.path.basename(source_path))
                print(f"      📡 CFDP Put initiated: {source_path} → N{dst_node}")
                return True

    def detach(self):
        """Detach from the ION proxy."""
        if self.proxy:
            self.proxy = None

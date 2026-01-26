#!/usr/bin/env python3
import time
import sys
from emion import Node

def setup_linear_topology(node: Node):
    """
    Sets up a linear topology: Node 1 <-> Node 2 <-> Node 3 <-> Node 4
    All on Region 1.
    """
    print("[INFO] Setting up linear topology: 1 <-> 2 <-> 3 <-> 4")
    
    # Common parameters
    # ION uses absolute timestamps (seconds since epoch)
    now = int(time.time())
    start_time = now        
    end_time = now + 3600     # +1 Hour
    rate = 1000000      # 1 MB/s
    owlt = 1            # 1 second delay
    region = 1

    # Connections
    links = [(1, 2), (2, 3), (3, 4)]
    
    for (n1, n2) in links:
        # Forward Contact
        node.add_contact(region, start_time, end_time, n1, n2, rate)
        # Reverse Contact (for acks/symmetry)
        node.add_contact(region, start_time, end_time, n2, n1, rate)
        
        # Forward Range
        node.add_range(start_time, end_time, n1, n2, owlt)
        # Reverse Range
        node.add_range(start_time, end_time, n2, n1, owlt)
        
        print(f"[TOPO] Added link {n1} <-> {n2}")

def main():
    print("--- 4-Node Linear Communication Test ---")
    
    try:
        with Node() as node:
            print("[ION] Attached to local node.")
            
            # 1. Setup the Contact Graph Routing (CGR) plan
            setup_linear_topology(node)
            
            # 2. Send a Bundle from Node 1 to Node 4
            # Since we are on Node 1, CGR should calculate the path 1->2->3->4
            # and forward the bundle to the next hop (Node 2).
            # Source must be a local, registered endpoint (e.g. 1.1).
            source = "ipn:1.1" # Using existing endpoint from host.rc
            dest = "ipn:4.1"   # Destination on Node 4
            payload = b"Linear Hop Payload: Hello Node 4 from Node 1!"
            
            print(f"\n[SEND] Sending bundle from {source} to {dest}")
            print(f"[SEND] Payload size: {len(payload)} bytes")
            
            node.send(source, dest, payload)
            
            print("[SUCCESS] Bundle successfully handed to ION Bundle Protocol Agent.")
            print("[INFO] Check 'ion.log' to see if it queued for Neighbor Node 2.")

    except RuntimeError as e:
        print(f"[ERROR] ION Interaction failed: {e}")
        print("Ensure ION is running: ./start_ion.sh")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

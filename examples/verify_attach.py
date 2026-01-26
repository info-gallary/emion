from emion import Node
import sys

print("Attempting to attach to ION...")
try:
    with Node() as node:
        print("[SUCCESS] Attached to ION.")
        
        print("Adding contact...")
        node.add_contact(1, 0, 3600, 1, 2, 100000)
        print("[SUCCESS] Contact added.")
        
        print("Sending bundle...")
        node.send("ipn:1.1", "ipn:2.1", b"Test Payload")
        print("[SUCCESS] Bundle sent.")
        
except Exception as e:
    print(f"[FAILURE] {e}")
    sys.exit(1)

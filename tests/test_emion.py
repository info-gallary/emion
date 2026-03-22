"""
EmION Consolidated Test — Real ION-DTN Two-Node Communication
Boots 2 authentic ION nodes, attaches pyion engines, sends a bundle
from Node 1 → Node 2, and verifies it arrives.

Run:
    python -m tests.test_emion
    OR
    python tests/test_emion.py
"""

import os
import sys
import time
import signal
import subprocess

# Ensure emion package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from emion.core.node import EmionNode
from emion.core.engine import EmionEngine


# Hard timeout so the script never hangs
def _timeout(signum, frame):
    print("\n[TEST] ⏰ TIMEOUT — test took too long, aborting.")
    subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(1)

signal.signal(signal.SIGALRM, _timeout)
signal.alarm(90)  # 90 s hard limit


def cleanup():
    """Kill any leftover ION daemons."""
    subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


def test_full_suite():
    """
    Consolidated Test Suite:
      1. Two-Node Basic Communication
      2. Anomaly Detection Integration
    """
    print("\n" + "=" * 60)
    print("  ⚛️  EmION Professional Test Suite")
    print("=" * 60)

    # ── Test 1: Basic 2-Node Comm ───────────────────
    print("\n[STEP 1] Verifying Basic 2-Node Communication...")
    node1 = EmionNode(1)
    node2 = EmionNode(2)
    node1.connect_to(2)
    node2.connect_to(1)

    try:
        cleanup()
        print("[TEST] Booting nodes...")
        node1.start(cleanup=False)
        node2.start(cleanup=False)
        
        # INCREASED STABILIZATION
        print("[TEST] Waiting for ION to settle (15s)...")
        time.sleep(15)

        import multiprocessing

        def receiver_process(q):
            try:
                e2 = EmionEngine(2)
                e2.attach()
                data = e2.receive("ipn:2.1", timeout=15)
                q.put(data)
            except Exception as e:
                q.put(None)

        print("[TEST] Attaching engine 1...")
        engine1 = EmionEngine(1)
        engine1.attach()

        print("[TEST] Spawning engine 2 receiver process...")
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=receiver_process, args=(q,))
        p.start()
        
        # Give receiver a second to attach and block on receive
        time.sleep(2)

        payload = b"EMION_BASIC_VERIFICATION"
        print("[TEST] Sending payload from Node 1...")
        engine1.send("ipn:1.1", "ipn:2.1", payload)
        
        p.join(timeout=16)
        received = None
        if not q.empty():
            received = q.get()

        if not (received and payload in received):
            print("❌ Basic communication failed!")
            return False
        print("✅ Basic communication passed.")

        # ── Test 2: Anomaly Detection ────────────────
        print("\n[STEP 2] Verifying Anomaly Module Integration...")
        
        # Start Dashboard and Sample Detector
        dash_proc = subprocess.Popen(["emion", "dashboard", "--port", "8420"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        det_proc = subprocess.Popen(["python3", "anomaly_detector.py", "--port", "8421"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10) # Give more time for boot

        import requests
        dash_url = "http://localhost:8420"
        mod_url = "http://localhost:8421"

        # Register nodes in dashboard so it knows about them
        requests.post(f"{dash_url}/api/nodes?node_id=1")
        requests.post(f"{dash_url}/api/nodes?node_id=2")
        
        # Important: Dashboard's /api/start runs its own subprocesses. 
        # But we already started ION nodes above for Step 1.
        # We need to reuse them or clean them up.
        # Let's register the anomaly module first.
        print("[TEST] Attaching Anomaly Module...")
        conn_resp = requests.post(f"{dash_url}/api/modules/connect?url={mod_url}&name=TestDetector")
        mod_json = conn_resp.json()
        print(f"       Connect response: {mod_json}")
        
        actual_name = mod_json.get("name", "Heuristic Detector v1")

        # Send malicious bundle via Dashboard API
        # We use a manual 'engines' injection trick for test or just rely on the existing engines
        # But wait, the Dashboard needs to have 'engines' populated.
        # Let's call /api/start in the dashboard - it will handle cleanup and restart.
        print("[TEST] Re-starting ION via Dashboard for Step 2...")
        requests.post(f"{dash_url}/api/start")
        time.sleep(12)

        print("[TEST] Sending 'MALICIOUS' bundle via Dashboard...")
        resp = requests.post(f"{dash_url}/api/send?from_node=1&to_node=2&payload=MALICIOUS_DATA_999")
        result = resp.json()
        print(f"       Send result: {result}")

        det_result = result.get("modules", {}).get(actual_name, {})
        if det_result.get("is_anomaly"):
            print("✅ Anomaly detection passed.")
        else:
            print(f"❌ Anomaly detection failed! Result: {det_result}")
            return False

        print("\n" + "=" * 60)
        print("  ✅ ALL TESTS PASSED SUCCESSFULLY!")
        print("=" * 60 + "\n")
        
        # Shutdown procs
        dash_proc.terminate()
        det_proc.terminate()
        return True

    except Exception as e:
        print(f"\n[TEST] ERROR: {e}")
        return False
    finally:
        cleanup()

if __name__ == "__main__":
    success = test_full_suite()
    sys.exit(0 if success else 1)

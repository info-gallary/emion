"""
Emion Network - High-level orchestration API for ION-DTN.
Provides simple functional interface for notebooks and scripts.
"""

import time
import subprocess
from typing import List, Dict, Optional
from emion.core.node import EmionNode
from emion.core.engine import EmionEngine
from emion.plugins.base import APIPlugin

_nodes: Dict[int, EmionNode] = {}
_engines: Dict[int, EmionEngine] = {}
_plugins: Dict[str, APIPlugin] = {}


def register_node(node_id: int):
    """Register an authentic ION-DTN node."""
    if node_id in _nodes:
        return _nodes[node_id]
    
    n = EmionNode(node_id)
    # auto-connect routing
    for existing_id, existing_node in _nodes.items():
        n.connect_to(existing_id)
        existing_node.connect_to(node_id)
    
    _nodes[node_id] = n
    return n


def start_core(cleanup: bool = True):
    """
    Boot all registered ION nodes. 
    Minimum 2 nodes recommended for routing verification.
    """
    if cleanup:
        print("[EmION] Cleaning up existing ION processes (killm)...")
        subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

    print(f"[EmION] Initializing {len(_nodes)} nodes...")
    for nid, node in _nodes.items():
        node.start(cleanup=False)
    
    # Wait for shared memory regions to stabilize
    time.sleep(6)
    
    print("[EmION] Attaching bundle engines...")
    for nid in _nodes:
        eng = EmionEngine(nid)
        eng.attach()
        _engines[nid] = eng


def stop_core():
    """Shut down all ION nodes and engines."""
    for nid, node in _nodes.items():
        try:
            node.stop()
        except:
            pass
    _engines.clear()
    subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def send_bundle(src: int, dst: int, payload: str):
    """Send a real BPv7 bundle via IPN."""
    if src not in _engines:
        raise RuntimeError(f"Engine for Node {src} not initialized. Call start_core() first.")
    
    src_eid = f"ipn:{src}.1"
    dst_eid = f"ipn:{dst}.1"
    data = payload.encode()
    
    res = _engines[src].send(src_eid, dst_eid, data)
    
    # Analyze with plugins
    module_results = {}
    for name, plugin in _plugins.items():
        module_results[name] = plugin.analyze(data, {"src": src_eid, "dst": dst_eid})
        
    return {
        "status": "sent",
        "bundle_id": res, 
        "src": src_eid, 
        "dst": dst_eid, 
        "size": len(data),
        "analyzer_results": module_results
    }


def attach_plugin(url: str, target_nodes: str = "all"):
    """Attach an external anomaly/security module."""
    plugin = APIPlugin(base_url=url, name=url)
    if plugin.health_check():
        _plugins[url] = plugin
        return {"status": "ok", "url": url}
    else:
        raise ConnectionError(f"Could not reach plugin at {url}/health")

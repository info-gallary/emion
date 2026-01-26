#!/usr/bin/env python3
"""
Health Check for emion module.
Verifies that all required C extension symbols are present and callable.
"""
import sys
import emion
from emion import Node

def check_symbol(module, name):
    if not hasattr(module, name):
        print(f"[FAIL] Missing symbol: {name}")
        return False
    print(f"[PASS] Found symbol: {name}")
    return True

def run_health_check():
    print(f"Checking emion version: {emion.__version__}")
    print(f"C Extension status: {emion.c_version()}")
    
    if "C extension not loaded" in emion.c_version():
        print("[CRITICAL] C Extension failed to load properly.")
        sys.exit(1)

    required_functions = [
        "ion_attach", "ion_detach",
        "bp_attach", "bp_detach", "bp_send",
        "add_contact", "remove_contact",
        "add_range", "remove_range"
    ]

    all_pass = True
    for func in required_functions:
        if not check_symbol(emion, func):
            all_pass = False

    print("\nChecking Node class API...")
    node = Node()
    node_methods = [
        "attach", "detach", "send",
        "add_contact", "remove_contact",
        "add_range", "remove_range"
    ]
    for method in node_methods:
        if not hasattr(node, method):
            print(f"[FAIL] Node missing method: {method}")
            all_pass = False
        else:
            print(f"[PASS] Node has method: {method}")

    if all_pass:
        print("\n[SUCCESS] Emion module is healthy and all symbols are present.")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some symbols are missing.")
        sys.exit(1)

if __name__ == "__main__":
    run_health_check()

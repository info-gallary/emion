#!/bin/bash
# ⚛️ EmION Unified Setup & Installation Script

set -e

echo "============================================================"
echo "  ⚛️ EmION — Authentic ION-DTN Setup"
echo "============================================================"

# 1. Dependency Check
echo "[SETUP] Checking dependencies..."
for cmd in ionadmin bpadmin ipnadmin python3 pip; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ Error: $cmd not found. Please install ION-DTN and Python 3."
        exit 1
    fi
done
echo "✅ Dependencies present."

# 2. Package Installation
echo "[SETUP] Installing EmION package and dashboard extras..."
pip install -e ".[dashboard]"

# 3. Environment Check
echo "[SETUP] Verifying environment..."
export PATH="$PATH:$HOME/.local/bin"
emion info

echo "============================================================"
echo "  ✅ INSTALLATION COMPLETE!"
echo "============================================================"
echo "  Quick Start:"
echo "    - Run Tests: python3 tests/test_emion.py"
echo "    - Dashboard: emion dashboard"
echo "============================================================"

#!/bin/bash
# ⚛️ EmION Unified Setup & Installation Script
# This script handles EmION installation and automatically bootstraps
# ION-DTN and pyion if they are missing from the system.

set -e

echo "============================================================"
echo "  ⚛️ EmION — Authentic ION-DTN Setup"
echo "============================================================"

# 1. Dependency Check & Bootstrap
echo "[SETUP] Checking system dependencies..."

# --- ION-DTN Bootstrap ---
if ! command -v ionadmin &> /dev/null; then
    echo "⚠️ ION-DTN not found. Entering Bootstrap Mode..."
    if [ -d "ION-DTN" ]; then
        echo "[BOOTSTRAP] Building ION-DTN from Project Source..."
        cd ION-DTN
        ./configure
        make -j$(nproc)
        sudo make install
        sudo ldconfig
        cd ..
        echo "✅ ION-DTN installed successfully."
    else
        echo "❌ Error: ION-DTN source directory not found. Cannot bootstrap."
        exit 1
    fi
else
    echo "✅ ION-DTN already present."
fi

# 2. EmION Package Installation
echo "[SETUP] Installing EmION package (with internal pyion C-bindings)..."
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

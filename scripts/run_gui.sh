#!/bin/bash
# run_gui.sh

# Get absolute path to ion-install
ION_INSTALL_DIR="$(pwd)/ion-install"

if [ ! -d "$ION_INSTALL_DIR" ]; then
    echo "Error: ion-install directory not found at $ION_INSTALL_DIR"
    exit 1
fi

# Export necessary environment variables for ION to function
export PATH="$ION_INSTALL_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$ION_INSTALL_DIR/lib:$LD_LIBRARY_PATH"
export ION_NODE_LIST_DIR="$(pwd)"

echo "Starting GUI Simulator with ION environment..."
python3 examples/gui_sim.py

#!/bin/bash
# stop_ion.sh

# Get absolute path to ion-install
ION_INSTALL_DIR="$(pwd)/ion-install"

if [ ! -d "$ION_INSTALL_DIR" ]; then
    echo "Error: ion-install directory not found at $ION_INSTALL_DIR"
    exit 1
fi

export PATH="$ION_INSTALL_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$ION_INSTALL_DIR/lib:$LD_LIBRARY_PATH"

echo "Stopping ION..."
ionstop

echo "ION stopped."

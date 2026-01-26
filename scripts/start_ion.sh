#!/bin/bash
# start_ion.sh

# Get absolute path to ion-install
ION_INSTALL_DIR="$(pwd)/ion-install"

if [ ! -d "$ION_INSTALL_DIR" ]; then
    echo "Error: ion-install directory not found at $ION_INSTALL_DIR"
    exit 1
fi

export PATH="$ION_INSTALL_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$ION_INSTALL_DIR/lib:$LD_LIBRARY_PATH"
export ION_NODE_LIST_DIR="$(pwd)"


echo "Cleaning up any previous ION instance..."
ionstop

# Force kill just in case
killm

# Aggressively clean up stale POSIX semaphores that killm might miss
# ION semaphores often look like sem.ion* or similar in /dev/shm
if [ -d "/dev/shm" ]; then
    echo "Cleaning stale semaphores from /dev/shm..."
    find /dev/shm -name "sem.ion*" -delete
    find /dev/shm -name "sem.*ion*" -delete
fi

# Remove potentially conflicting config files
rm -f ion_nodes ion.log
# Wait a moment for cleanup
sleep 2

echo "Starting ION node 1..."
ionstart -I host.rc

echo "ION successfully started."
echo "You can now run the GUI simulator: python3 examples/gui_sim.py"


#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

NODE_NAME="$(hostname)"
NODE_NUM="${NODE_NAME#n}"

ION_BIN="/usr/local/bin"
ION_CFG="${SCRIPT_DIR}/config"
IONRC="${SCRIPT_DIR}/${NODE_NAME}.ionrc"
BPRC="${ION_CFG}/${NODE_NAME}.bprc"
IPNRC="${ION_CFG}/${NODE_NAME}.ipnrc"
LTPRC="${ION_CFG}/${NODE_NAME}.ltprc"

export PATH="${ION_BIN}:$PATH"

bash "${SCRIPT_DIR}/rcgen.sh" "${NODE_NUM}"
ionstart -i "${IONRC}" -b "${BPRC}" -p "${IPNRC}" -l "${LTPRC}"
sleep 2
echo "[ION] Started on ${NODE_NAME}"

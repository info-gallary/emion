#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="${HOME}/.local/share/core-gui-novnc"
NOVNC_DIR="${RUNTIME_DIR}/noVNC"
TIGER_DIR="${RUNTIME_DIR}/tigervnc"
CORE_USER_DIR="${HOME}/.local/share/core-user"
DISPLAY_NUM="${CORE_VNC_DISPLAY:-:2}"
VNC_PORT="${CORE_VNC_PORT:-5902}"
NOVNC_PORT="${CORE_NOVNC_PORT:-6082}"

mkdir -p "${RUNTIME_DIR}"

install_websockify() {
  if ! python3 -m websockify --help >/dev/null 2>&1; then
    python3 -m pip install --user websockify
  fi
}

install_novnc() {
  if [[ ! -d "${NOVNC_DIR}/app" ]]; then
    git clone --depth 1 https://github.com/novnc/noVNC.git "${NOVNC_DIR}"
  fi
}

install_tigervnc() {
  if [[ ! -x "${TIGER_DIR}/usr/bin/Xtigervnc" ]]; then
    rm -rf "${TIGER_DIR}"
    mkdir -p "${TIGER_DIR}"
    (
      cd "${RUNTIME_DIR}"
      apt download tigervnc-standalone-server tigervnc-common >/dev/null
    )
    for deb in "${RUNTIME_DIR}"/tigervnc-common_*_amd64.deb "${RUNTIME_DIR}"/tigervnc-standalone-server_*_amd64.deb; do
      dpkg-deb -x "${deb}" "${TIGER_DIR}"
    done
  fi
}

start_vnc_display() {
  if ! ss -ltn "( sport = :${VNC_PORT} )" | tail -n +2 | grep -q .; then
    nohup "${TIGER_DIR}/usr/bin/Xtigervnc" "${DISPLAY_NUM}" \
      -localhost=1 \
      -SecurityTypes None \
      -geometry 1280x800 \
      -depth 24 \
      >"${RUNTIME_DIR}/Xtigervnc.log" 2>&1 &
    sleep 2
  fi
}

start_core_daemon() {
  if ! ss -ltn "( sport = :50051 )" | tail -n +2 | grep -q .; then
    nohup env \
      PATH="${CORE_USER_DIR}/bin:${PATH}" \
      LD_LIBRARY_PATH="${CORE_USER_DIR}/lib:${LD_LIBRARY_PATH:-}" \
      python3 -m core.scripts.daemon \
      -c "${CORE_USER_DIR}/etc/core.conf" \
      -l "${CORE_USER_DIR}/etc/logging.conf" \
      >"${CORE_USER_DIR}/core-daemon.log" 2>&1 &
    sleep 2
  fi
}

start_core_gui() {
  if ! pgrep -af "DISPLAY=${DISPLAY_NUM} .*core-gui|core\\.scripts\\.gui" >/dev/null 2>&1; then
    nohup env DISPLAY="${DISPLAY_NUM}" /home/moss/.local/bin/core-gui \
      >"${RUNTIME_DIR}/core-gui.log" 2>&1 &
    sleep 2
  fi
}

start_novnc() {
  if ! ss -ltn "( sport = :${NOVNC_PORT} )" | tail -n +2 | grep -q .; then
    nohup python3 -m websockify \
      --web "${NOVNC_DIR}" \
      "${NOVNC_PORT}" \
      "127.0.0.1:${VNC_PORT}" \
      >"${RUNTIME_DIR}/websockify.log" 2>&1 &
    sleep 2
  fi
}

main() {
  if [[ ! -x "/home/moss/.local/bin/core-gui" ]]; then
    echo "core-gui is not installed at /home/moss/.local/bin/core-gui" >&2
    exit 1
  fi

  install_websockify
  install_novnc
  install_tigervnc
  start_vnc_display
  start_core_daemon
  start_core_gui
  start_novnc

  cat <<EOF
noVNC is available at:
  http://127.0.0.1:${NOVNC_PORT}/vnc.html?autoconnect=1&resize=remote

Backend:
  Display: ${DISPLAY_NUM}
  VNC:     ${VNC_PORT}
  noVNC:   ${NOVNC_PORT}

Logs:
  ${RUNTIME_DIR}/Xtigervnc.log
  ${RUNTIME_DIR}/core-gui.log
  ${RUNTIME_DIR}/websockify.log
  ${CORE_USER_DIR}/core-daemon.log
EOF
}

main "$@"

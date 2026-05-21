"""
EmionNode — Authentic ION-DTN node manager.
Generates ION configs and boots real C daemons (ionadmin, bpadmin, etc.).
Uses pyion for all communication. No dummies/proxies.
"""

import os
import subprocess
import time
import shutil
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


class EmionNode:
    """
    Manages one authentic ION-DTN node.
    Auto-generates config files and boots the real C-engine daemons.
    """

    def __init__(self, node_id: int, base_dir: str = "/tmp/emion_nodes"):
        self.node_id = node_id
        self.base_dir = base_dir
        self.node_dir = os.path.join(base_dir, str(node_id))
        self.ipn = f"ipn:{node_id}"
        self.port = 4556 + node_id
        self.ion_log = os.path.join(self.node_dir, "ion.log")
        self.is_running = False
        self._peers = []
        self._last_resource_sample_ts = None

    @property
    def node_path(self) -> Path:
        return Path(self.node_dir)

    def _setup_dir(self):
        """Create a clean working directory for this node."""
        if os.path.exists(self.node_dir):
            shutil.rmtree(self.node_dir)
        os.makedirs(self.node_dir, exist_ok=True)

    def _generate_configs(self):
        """Generate all ION configuration files for this node."""
        d = self.node_dir

        # ionconfig — SDR and working-memory parameters
        with open(os.path.join(d, "node.ionconfig"), "w") as f:
            wm_key = 65280 + int(self.node_id)
            f.write(
                f"wmKey {wm_key}\n"
                f"wmSize 50000000\n"
                f"wmAddress 0\n"
                f"sdrName 'ion'\n"
                f"sdrWmSize 0\n"
                f"configFlags 1\n"
                f"heapWords 500000\n"
                f"pathName '{d}'\n"
            )

        # ionrc — initialise the ION node
        with open(os.path.join(d, "node.ionrc"), "w") as f:
            f.write(f"1 {self.node_id} node.ionconfig\ns\nm horizon +0\n")
            # Add contact and range for each peer
            for peer_id in self._peers:
                f.write(f"a contact +0 +3600 {self.node_id} {peer_id} 1000000\n")
                f.write(f"a contact +0 +3600 {peer_id} {self.node_id} 1000000\n")
                f.write(f"a range +0 +3600 {self.node_id} {peer_id} 1\n")
                f.write(f"a range +0 +3600 {peer_id} {self.node_id} 1\n")

        # ionsecrc — security (minimal)
        with open(os.path.join(d, "node.ionsecrc"), "w") as f:
            f.write("1\n")

        # bprc — bundle protocol
        with open(os.path.join(d, "node.bprc"), "w") as f:
            f.write(
                f"1\n"
                f"a scheme ipn 'ipnfw' 'ipnadminep'\n"
                f"a endpoint {self.ipn}.0 x\n"
                f"a endpoint {self.ipn}.1 x\n"
                f"a endpoint {self.ipn}.2 x\n"
                f"a endpoint {self.ipn}.64 x\n"
                f"a protocol udp 1400 100 125000\n"
                f"a induct udp 127.0.0.1:{self.port} udpcli\n"
            )
            f.write(f"a outduct udp 127.0.0.1:{self.port} udpclo\n")
            for peer_id in self._peers:
                peer_port = 4556 + peer_id
                f.write(f"a outduct udp 127.0.0.1:{peer_port} udpclo\n")
            f.write("w 1\ns\n")

        # ipnrc — routing plans
        with open(os.path.join(d, "node.ipnrc"), "w") as f:
            # Local delivery
            f.write(f"a plan {self.node_id} .\n")
            # For all other nodes, use CGR (Contact Graph Routing)
            for peer_id in self._peers:
                peer_port = 4556 + peer_id
                f.write(f"a plan {peer_id} udp/127.0.0.1:{peer_port}\n")
            # Default to CGR for any unknown nodes
            f.write("a plan * cgr\n")

        # start.sh — native bash launcher
        start_sh = os.path.join(d, "start.sh")
        with open(start_sh, "w") as f:
            f.write(
                "#!/bin/bash\n"
                f"cd {d}\n"
                "export PATH=\"$PATH:/usr/local/bin\"\n"
                "ionadmin node.ionrc\n"
                "ionsecadmin node.ionsecrc\n"
                "bpadmin node.bprc\n"
                "ipnadmin node.ipnrc\n"
                "echo 'ION Core initialized.'\n"
            )
        os.chmod(start_sh, 0o755)

    def connect_to(self, peer_node_id: int):
        """Register a routing plan to reach another node."""
        if peer_node_id not in self._peers:
            self._peers.append(peer_node_id)

    def start(self, cleanup=True, startup_wait: float = 6.0):
        """Boot the authentic ION C-engine daemons."""
        if cleanup:
            # Aggressive cleanup
            subprocess.run(["killm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "ionadmin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "bpadmin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "ipnadmin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "ltpadmin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)

        self._setup_dir()
        print(f"[EmION] Generating node {self.node_id} config...")
        self._generate_configs()

        print(f"[EmION] Booting ION C-engine (Node {self.node_id}, port {self.port})...")
        log_path = os.path.join(self.node_dir, "node_boot.log")
        with open(log_path, "w") as log_file:
            subprocess.Popen(
                ["./start.sh"],
                cwd=self.node_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        # Wait for ION to stabilize
        time.sleep(max(startup_wait, 0.0))
        self.is_running = True
        self._prime_resource_sampling()
        print(f"      ✅ Node {self.node_id} LIVE  (ipn:{self.node_id}, udp:{self.port})")

    def stop(self):
        """Shut down all ION daemons."""
        print(f"[EmION] Stopping Node {self.node_id}...")
        subprocess.run(["ionstop"], cwd=self.node_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        self.is_running = False

    def _iter_node_processes(self):
        if psutil is None:
            return []

        node_dir = str(self.node_path.resolve())
        processes = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.cwd() == node_dir:
                    processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                continue
        return processes

    def _prime_resource_sampling(self):
        if psutil is None:
            return
        for proc in self._iter_node_processes():
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._last_resource_sample_ts = time.time()

    def get_resource_usage(self) -> dict:
        """Measure per-node resource usage from the real ION daemon set."""
        if psutil is None or not self.is_running:
            return {
                "available": False,
                "process_count": 0,
                "cpu_percent": 0.0,
                "rss_bytes": 0,
                "vms_bytes": 0,
                "sample_window_s": 0.0,
                "processes": [],
            }

        now = time.time()
        sample_window = 0.0 if self._last_resource_sample_ts is None else max(now - self._last_resource_sample_ts, 0.0)
        processes = []
        total_cpu = 0.0
        total_rss = 0
        total_vms = 0
        for proc in self._iter_node_processes():
            try:
                mem = proc.memory_info()
                cpu = proc.cpu_percent(interval=None)
                processes.append({
                    "pid": proc.pid,
                    "name": proc.name(),
                    "cpu_percent": round(cpu, 3),
                    "rss_bytes": int(mem.rss),
                    "vms_bytes": int(mem.vms),
                })
                total_cpu += cpu
                total_rss += mem.rss
                total_vms += mem.vms
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self._last_resource_sample_ts = now
        return {
            "available": True,
            "process_count": len(processes),
            "cpu_percent": round(total_cpu, 3),
            "rss_bytes": int(total_rss),
            "vms_bytes": int(total_vms),
            "sample_window_s": round(sample_window, 3),
            "processes": processes,
        }

    def get_ion_log_tail(self, max_lines: int = 20) -> list[str]:
        path = Path(self.ion_log)
        if not path.exists():
            return []
        try:
            return path.read_text(errors="ignore").splitlines()[-max_lines:]
        except OSError:
            return []

    def get_system_telemetry(self) -> dict:
        """Get real-time ION system telemetry."""
        if not self.is_running:
            return {}
        try:
            res = subprocess.run(
                ["ionadmin", "m info"],
                cwd=self.node_dir,
                capture_output=True,
                text=True,
                timeout=1
            )
            sdr_info = {}
            for line in res.stdout.splitlines():
                if "wmKey" in line: sdr_info["wmKey"] = line.split()[-1]
                if "wmSize" in line: sdr_info["wmSize"] = line.split()[-1]
            return {
                "node_id": self.node_id,
                "sdr": sdr_info,
                "resources": self.get_resource_usage(),
                "ion_log_tail": self.get_ion_log_tail(),
                "timestamp": time.time(),
            }
        except Exception:
            return {}

    def status(self) -> dict:
        """Return node status information."""
        boot_log = ""
        log_path = os.path.join(self.node_dir, "node_boot.log")
        if os.path.exists(log_path):
            with open(log_path) as f:
                boot_log = f.read()
        return {
            "node_id": self.node_id,
            "is_running": self.is_running,
            "port": self.port,
            "ipn": self.ipn,
            "peers": list(self._peers),
            "boot_log": boot_log,
            "telemetry": self.get_system_telemetry()
        }

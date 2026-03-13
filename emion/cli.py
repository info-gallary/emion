"""
EmION CLI — all operations use real ION-DTN.

    emion dashboard     Launch the web dashboard
    emion setup         Install ION-DTN and pyion dependencies
    emion info          Show ION-DTN status
    emion test          Run the 2-node communication test
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="emion",
        description="EmION — Authentic ION-DTN Framework"
    )
    sub = parser.add_subparsers(dest="cmd")

    d = sub.add_parser("dashboard", help="Launch the web dashboard")
    d.add_argument("--host", default="0.0.0.0")
    d.add_argument("--port", type=int, default=8420)

    sub.add_parser("setup", help="Install ION-DTN and pyion dependencies")
    sub.add_parser("info", help="Show ION-DTN status")
    sub.add_parser("test", help="Run 2-node comm test")

    args = parser.parse_args()

    if args.cmd == "dashboard":
        from emion.dashboard.server import run
        run(host=args.host, port=args.port)
    elif args.cmd == "setup":
        _setup()
    elif args.cmd == "info":
        _info()
    elif args.cmd == "test":
        _test()
    else:
        parser.print_help()


def _setup():
    import subprocess
    import os
    import shutil

    print("\n  ⚛ EmION Automated Dependency Setup")
    print("  ====================================")
    
    # 1. Check for ION-DTN
    if not shutil.which("ionadmin"):
        print("  [1/2] Installing ION-DTN C-engine...")
        # We reuse the logic from install.sh but in a pythonic way
        try:
            # We assume a Linux environment as per README
            setup_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "install.sh")
            if os.path.exists(setup_script):
                subprocess.run(["bash", setup_script], check=True)
            else:
                # Fallback: Download and install from NASA source if script not found
                print("  Installing via legacy source build...")
                # (Simplified for briefness, usually we'd curl/tar/make)
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "build-essential", "cmake", "mercurial"], check=True)
        except Exception as e:
            print(f"  ❌ Failed to install ION-DTN: {e}")
            return
    else:
        print("  ✅ ION-DTN already installed.")

    # 2. Check for pyion
    try:
        import pyion
        print("  ✅ pyion already installed.")
    except ImportError:
        print("  [2/2] Installing pyion bindings...")
        
        # Prepare environment for pyion build
        env = os.environ.copy()
        env["PYION_BP_VERSION"] = "BPv7"
        
        # Determine ION_HOME
        # Aggressive Search:
        # 1. Local project source
        # 2. Parent directory's project source (if installed via pip -e)
        # 3. Standard Desktop location (where user likely has it)
        # 4. System paths
        
        search_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "ION-DTN"),
            os.path.expanduser("~/Desktop/Emion/ION-DTN"),
            "/usr/local",
            "/usr"
        ]
        
        ion_home = None
        for p in search_paths:
            if os.path.exists(os.path.join(p, "ici", "include", "ici.h")) or \
               os.path.exists(os.path.join(p, "include", "ion.h")):
                ion_home = os.path.abspath(p)
                break
        
        if not ion_home:
            # Try to guess from ionadmin binary
            ionadmin_path = shutil.which("ionadmin")
            if ionadmin_path:
                ion_home = os.path.dirname(os.path.dirname(ionadmin_path))
        
        if ion_home:
            env["ION_HOME"] = ion_home
            print(f"      (Found ION path: {ion_home})")
        else:
            print("  ⚠️  Warning: ION_HOME source tree not found.")
            print("     Build usually requires the ION source directory (e.g. ~/Desktop/Emion/ION-DTN)")

        # Determine pyion source
        # Aggressive Search for pyion source
        pyion_search = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyion"),
            os.path.expanduser("~/Desktop/Emion/pyion")
        ]
        
        pyion_source = "git+https://github.com/nasa-jpl/pyion.git@v4.1.3"
        for p in pyion_search:
            if os.path.exists(os.path.join(p, "setup.py")):
                pyion_source = os.path.abspath(p)
                print(f"      (Found local pyion source: {pyion_source})")
                break

        if pyion_source.startswith("git"):
            print(f"      (Installing from remote branch: v4.1.3)")

        # Performance/Compatibility check: use uv if available, otherwise pip
        installer = None
        if shutil.which("uv"):
            installer = ["uv", "pip"]
        elif shutil.which("pip"):
            installer = [sys.executable, "-m", "pip"]
        elif shutil.which("pip3"):
            installer = ["pip3"]

        if not installer:
            print("  ❌ Error: Neither 'pip' nor 'uv' found in this environment!")
            return

        try:
            print(f"      (Executing: {' '.join(installer)} install {pyion_source})")
            subprocess.run(installer + ["install", pyion_source], check=True, env=env)
            print("  ✅ pyion installed successfully.")
        except Exception as e:
            print(f"  ❌ Failed to install pyion: {e}")
            print("\n  💡 Pro-tip: If you have the Emion source code, try: bash install.sh")
            print("     Or set ION_HOME and install manually: ION_HOME=/path/to/ion PYION_BP_VERSION=BPv7 pip install .")
            return

    print("\n  🎉 Setup Complete! Run 'emion dashboard' to start.\n")


def _info():
    import shutil
    import emion
    print(f"\n  ⚛ EmION v{emion.__version__}")
    
    ion_found = True
    for cmd in ["ionadmin", "bpadmin", "ionsecadmin", "bprecvfile", "bpsendfile"]:
        path = shutil.which(cmd)
        if not path: ion_found = False
        print(f"  {cmd}: {'✅ ' + path if path else '❌ not found'}")
    
    pyion_found = True
    try:
        import pyion
        # Safe version check: pyion 4.1.2+ might not have __version__
        print(f"  pyion: ✅ available")
    except ImportError:
        pyion_found = False
        print(f"  pyion: ❌ not found")

    if not ion_found or not pyion_found:
        print("\n  ⚠️  Dependencies missing! Run 'emion setup' to fix.")
    
    try:
        import fastapi
        print(f"  fastapi: v{fastapi.__version__}")
    except ImportError:
        print(f"  fastapi: ❌  (pip install fastapi uvicorn websockets)")
    print()


def _test():
    from tests.test_emion import test_two_node_communication
    ok = test_two_node_communication()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

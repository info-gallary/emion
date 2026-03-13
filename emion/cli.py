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
    import tempfile

    print("\n  ⚛ EmION Standalone Universal Setup")
    print("  ====================================")
    
    # 1. Check for ION-DTN
    if not shutil.which("ionadmin"):
        print("  [1/2] ION-DTN not found. Starting Autonomous Build...")
        
        try:
            # Install system dependencies
            print("      (Installing system build tools...)")
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", 
                          "build-essential", "cmake", "automake", "libtool", "wget", "tar"], check=True)
            
            # Download and Build ION-DTN
            with tempfile.TemporaryDirectory() as tmpdir:
                ion_url = "https://github.com/NASA-AMMOS/ION-DTN/archive/refs/tags/v4.1.2.tar.gz"
                print(f"      (Downloading ION-DTN v4.1.2...)")
                subprocess.run(["wget", ion_url, "-O", os.path.join(tmpdir, "ion.tar.gz")], check=True)
                subprocess.run(["tar", "-xzf", os.path.join(tmpdir, "ion.tar.gz"), "-C", tmpdir], check=True)
                
                # Find the extracted directory
                extracted_dir = None
                for d in os.listdir(tmpdir):
                    if os.path.isdir(os.path.join(tmpdir, d)) and "ION-DTN" in d:
                        extracted_dir = os.path.join(tmpdir, d)
                        break
                
                if not extracted_dir:
                    raise Exception("Failed to find extracted ION-DTN directory.")
                
                print(f"      (Compiling & Installing ION-DTN... this may take a few minutes)")
                # Build steps
                subprocess.run(["./configure"], cwd=extracted_dir, check=True)
                subprocess.run(["make", "-j", str(os.cpu_count() or 2)], cwd=extracted_dir, check=True)
                subprocess.run(["sudo", "make", "install"], cwd=extracted_dir, check=True)
                subprocess.run(["sudo", "ldconfig"], check=True)
                
            print("  ✅ ION-DTN installed globally.")
        except Exception as e:
            print(f"  ❌ Failed to autonomously install ION-DTN: {e}")
            print("     Manual fix: Download ION-DTN v4.1.2, run ./configure && make && sudo make install")
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
        # 1. Local project source (if current user has it)
        # 2. Parent directory (Emion project root)
        # 3. Standard locations (where we just installed it)
        
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
            # Guess from binary for global installs
            ionadmin_path = shutil.which("ionadmin")
            if ionadmin_path:
                ion_home = os.path.dirname(os.path.dirname(ionadmin_path))
        
        if ion_home:
            env["ION_HOME"] = ion_home
            print(f"      (Setting build context ION_HOME={ion_home})")
        
        # Determine pyion source
        # Note: We use v4.1.3 for its BPv7 stability
        pyion_source = "git+https://github.com/nasa-jpl/pyion.git@v4.1.3"
        
        # Check if we are in the source tree (developer mode)
        local_pyion = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyion")
        if os.path.exists(os.path.join(local_pyion, "setup.py")):
            pyion_source = os.path.abspath(local_pyion)
            print(f"      (Found local pyion source: {pyion_source})")
        else:
            print(f"      (Installing from GitHub: v4.1.3)")

        # Performance/Compatibility check: use uv if available, otherwise pip
        installer = None
        if shutil.which("uv"):
            installer = ["uv", "pip"]
        elif shutil.which("pip"):
            installer = [sys.executable, "-m", "pip"]
        elif shutil.which("pip3"):
            installer = ["pip3"]

        if not installer:
            print("  ❌ Error: Neither 'pip' nor 'uv' found!")
            return

        try:
            print(f"      (Executing: {' '.join(installer)} install {pyion_source})")
            subprocess.run(installer + ["install", pyion_source], check=True, env=env)
            print("  ✅ pyion installed successfully.")
        except Exception as e:
            print(f"  ❌ Failed to install pyion: {e}")
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

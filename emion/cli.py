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

    sub.add_parser("setup", help="Install ION-DTN and build pyion bindings")
    sub.add_parser("build", help="Manually build/rebuild pyion C-bindings")
    sub.add_parser("info", help="Show ION-DTN status")
    sub.add_parser("test", help="Run 2-node comm test")
    
    args = parser.parse_args()

    if args.cmd == "dashboard":
        from emion.dashboard.server import run
        run(host=args.host, port=args.port)
    elif args.cmd == "setup":
        _setup()
    elif args.cmd == "build":
        _build()
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
        print("  [1/1] ION-DTN not found. Starting Autonomous Build...")
        
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

    print("\n  🎉 ION-DTN Setup Complete!")
    _build()


def _build():
    import subprocess
    import shutil
    import sys
    import os
    from pathlib import Path

    print("\n  ⚛ EmION C-Extension Build")
    print("  ===========================")
    
    # Try to find the root of the package to run build
    import emion
    pkg_dir = Path(emion.__file__).parent.parent
    
    # Check if we are in a source tree or installed package
    if os.path.exists(pkg_dir / "setup.py"):
        root_dir = pkg_dir
    else:
        print("  [!] Running from installed package. Attempting force-reinstall build...")
        
        # Determine the installer (pip or uv)
        installer_cmd = [sys.executable, "-m", "pip", "install", "emion", "--force-reinstall", "--no-cache-dir"]
        
        # Try to detect if we should use uv instead of pip
        if not shutil.which("pip") and shutil.which("uv"):
             print("  [i] 'pip' not found, falling back to 'uv'...")
             installer_cmd = ["uv", "pip", "install", "emion", "--force-reinstall", "--no-cache"]

        try:
            subprocess.run(installer_cmd, check=True)
            print("  ✅ Bindings rebuilt successfully.")
            return
        except Exception as e:
            print(f"  ❌ Failed to rebuild: {e}")
            if "No module named pip" in str(e) and shutil.which("uv"):
                print("     (Tip: Your venv lacks pip. Try: 'uv pip install emion --force-reinstall --no-cache')")
            return

    print(f"  [1/1] Building extensions in {root_dir}...")
    try:
        subprocess.run([sys.executable, "setup.py", "build_ext", "--inplace"], cwd=root_dir, check=True)
        print("  ✅ Bindings built successfully.")
    except Exception as e:
        print(f"  ❌ Build failed: {e}")
        print("     Ensure ION-DTN is installed and headers are in /usr/local/include")


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
        from emion import pyion
        print(f"  pyion (internal): ✅ available")
    except ImportError as e:
        pyion_found = False
        print(f"  pyion (internal): ❌ not built or linked ({e})")
        print(f"  (Run: pip install emion --force-reinstall)")

    if not ion_found:
        print("\n  ⚠️  ION-DTN missing! Run 'emion setup' to fix.")
    
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

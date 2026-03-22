"""
EmION CLI — all operations use real ION-DTN.

    emion dashboard     Launch the web dashboard
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

    sub.add_parser("info", help="Show ION-DTN status")
    sub.add_parser("test", help="Run 2-node comm test")

    args = parser.parse_args()

    if args.cmd == "dashboard":
        from emion.dashboard.server import run
        run(host=args.host, port=args.port)
    elif args.cmd == "info":
        _info()
    elif args.cmd == "test":
        _test()
    else:
        parser.print_help()


def _info():
    import shutil
    import emion
    import emion.pyion as pyion

    print(f"\n  ⚛ EmION v{emion.__version__}")
    print(f"  pyion: v{pyion.__version__} (integrated)")

    # Get ION version via C-extension with source fallback
    ion_v = "Unknown"
    try:
        ion_v = pyion.get_ion_version()
        if not ion_v or "unknown" in ion_v.lower() or ion_v == "Unknown":
            import os
            # Try CWD/ION-DTN or emion/../ION-DTN
            bases = [os.getcwd(), os.path.dirname(os.path.dirname(emion.__file__))]
            for base in bases:
                conf_path = os.path.join(base, "ION-DTN", "configure.ac")
                if os.path.exists(conf_path):
                    with open(conf_path, "r") as f:
                        content = f.read()
                        import re
                        # More flexible regex for AC_INIT
                        match = re.search(r"AC_INIT\(\s*\[ion\s*\]\s*,\s*\[([\w\.-]+)\]", content)
                        if match:
                            ion_v = f"{match.group(1)} (source)"
                            break
            # If still unknown but ionadmin exists
            if (not ion_v or "Unknown" in ion_v) and shutil.which("ionadmin"):
                ion_v = "v4.1.x (installed)"
    except:
        pass

    print(f"  ION-DTN: {ion_v}")
    print("-" * 30)

    for cmd in ["ionadmin", "bpadmin", "ionsecadmin", "bprecvfile", "bpsendfile"]:
        path = shutil.which(cmd)
        print(f"  {cmd}: {'✅ ' + path if path else '❌ not found'}")

    try:
        import fastapi
        print(f"  fastapi: v{fastapi.__version__}")
    except ImportError:
        print(f"  fastapi: ❌  (pip install fastapi uvicorn websockets)")
    print()


def _test():
    import os
    import sys
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, "tests")):
        if cwd not in sys.path:
            sys.path.insert(0, cwd)
    else:
        pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if pkg_root not in sys.path:
            sys.path.insert(0, pkg_root)
            
    try:
        from tests.test_emion import test_full_suite
    except ImportError:
        print("❌ Cannot find 'tests' module. Are you running this from the EmION source directory?", file=sys.stderr)
        sys.exit(1)
        
    ok = test_full_suite()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

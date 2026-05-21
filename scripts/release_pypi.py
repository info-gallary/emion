#!/usr/bin/env python3
"""Small release helper for EmION PyPI publishes.

Examples:
  python3 scripts/release_pypi.py set-version 1.0.1
  python3 scripts/release_pypi.py build
  PYPI_API_TOKEN=... python3 scripts/release_pypi.py publish --token-env PYPI_API_TOKEN
  PYPI_API_TOKEN=... python3 scripts/release_pypi.py all 1.0.1 --token-env PYPI_API_TOKEN
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
WHEELHOUSE_DIR = ROOT / "wheelhouse"

VERSION_REWRITES = {
    "pyproject.toml": [
        (r'(?m)^version = "([^"]+)"$', 'version = "{version}"'),
    ],
    "setup.py": [
        (r'(?m)^(?P<indent>\s*)version="([^"]+)",$', '{indent}version="{version}",'),
    ],
    "emion/__init__.py": [
        (r'(?m)^__version__ = "([^"]+)"$', '__version__ = "{version}"'),
    ],
    "emion/dashboard/server.py": [
        (r'(?m)^(?P<indent>\s*)app = FastAPI\(title="EmION Dashboard", version="([^"]+)",$', '{indent}app = FastAPI(title="EmION Dashboard", version="{version}",'),
    ],
    "emion/dashboard/static/app.js": [
        (r'v\d+\.\d+\.\d+ · ION-DTN Simulation · Per-Node ML Modules', 'v{version} · ION-DTN Simulation · Per-Node ML Modules'),
    ],
    "emion/dashboard/static/index.html": [
        (r'EmION v\d+\.\d+\.\d+ — XML Research Suite', 'EmION v{version} — XML Research Suite'),
        (r'<span class="brand-ver">v\d+\.\d+\.\d+</span>', '<span class="brand-ver">v{version}</span>'),
    ],
    "CITATION.cff": [
        (r'(?m)^version: "([^"]+)"$', 'version: "{version}"'),
    ],
    "README.md": [
        (r'Package config \(v\d+\.\d+\)', 'Package config (v{major}.{minor})'),
    ],
}


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'(?m)^version = "([^"]+)"$', text)
    if not match:
        raise RuntimeError("Could not determine version from pyproject.toml")
    return match.group(1)


def set_version(version: str) -> None:
    major_minor = ".".join(version.split(".")[:2])
    for rel_path, rewrites in VERSION_REWRITES.items():
        path = ROOT / rel_path
        text = path.read_text()
        original = text
        for pattern, template in rewrites:
            def repl(match: re.Match[str]) -> str:
                indent = match.groupdict().get("indent", "")
                return template.format(version=version, major=version.split(".")[0], minor=version.split(".")[1], indent=indent)
            text = re.sub(pattern, repl, text, count=1)
        if text == original:
            raise RuntimeError(f"Did not update version marker in {rel_path}")
        path.write_text(text)
    print(f"Version updated to {version}")


def ensure_tool(module: str, package: str | None = None) -> None:
    package = package or module
    try:
        __import__(module)
    except Exception:
        run([sys.executable, "-m", "pip", "install", "--user", package])


def clean() -> None:
    for target in ("build", "dist", "wheelhouse", "emion.egg-info"):
        path = ROOT / target
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def build() -> None:
    ensure_tool("build")
    ensure_tool("auditwheel")
    ensure_tool("twine")
    ensure_tool("patchelf")

    clean()
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}:{env.get('PATH', '')}"
    run([sys.executable, "-m", "build"], env=env)
    run([sys.executable, "-m", "twine", "check", *map(str, sorted(DIST_DIR.glob("*")))], env=env)

    wheel = next(DIST_DIR.glob("*.whl"), None)
    if wheel is None:
        raise RuntimeError("No wheel produced in dist/")

    run([sys.executable, "-m", "auditwheel", "repair", "-w", str(WHEELHOUSE_DIR), str(wheel)], env=env)
    run([sys.executable, "-m", "twine", "check", *map(str, sorted(WHEELHOUSE_DIR.glob("*")))], env=env)


def publish(token_env: str) -> None:
    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(f"Missing PyPI token in environment variable {token_env}")

    env = os.environ.copy()
    env["TWINE_USERNAME"] = "__token__"
    env["TWINE_PASSWORD"] = token
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}:{env.get('PATH', '')}"

    sdists = sorted(DIST_DIR.glob("*.tar.gz"))
    wheels = sorted(WHEELHOUSE_DIR.glob("*.whl"))
    if not sdists:
        raise RuntimeError("No source distribution found in dist/")
    if not wheels:
        raise RuntimeError("No repaired wheels found in wheelhouse/")

    run([sys.executable, "-m", "twine", "upload", "--skip-existing", *map(str, sdists), *map(str, wheels)], env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release helper for EmION")
    sub = parser.add_subparsers(dest="cmd", required=True)

    setv = sub.add_parser("set-version", help="Update all version references")
    setv.add_argument("version")

    sub.add_parser("build", help="Build and repair distributions")

    pub = sub.add_parser("publish", help="Upload built artifacts to PyPI")
    pub.add_argument("--token-env", default="PYPI_API_TOKEN")

    all_cmd = sub.add_parser("all", help="Set version, build, and publish")
    all_cmd.add_argument("version")
    all_cmd.add_argument("--token-env", default="PYPI_API_TOKEN")

    args = parser.parse_args(argv)
    if args.cmd == "set-version":
        set_version(args.version)
    elif args.cmd == "build":
        build()
    elif args.cmd == "publish":
        publish(args.token_env)
    elif args.cmd == "all":
        set_version(args.version)
        build()
        publish(args.token_env)

    print(f"Current version: {current_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

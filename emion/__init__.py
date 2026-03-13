"""
EmION — Authentic ION-DTN Framework.
All operations use real ION C-engine + pyion. No dummies.
"""

__version__ = "0.3.9"
__author__ = "EmION Team"

try:
    from .core.node import EmionNode
    from .core.engine import EmionEngine
    from .plugins.base import APIPlugin
except ImportError:
    # Allow importing root package even if dependencies are missing (for setup)
    EmionNode = None
    EmionEngine = None
    APIPlugin = None

ION_AVAILABLE = True


def dashboard(host="0.0.0.0", port=8420):
    """Launch the EmION web dashboard."""
    from .dashboard.server import run
    run(host=host, port=port)

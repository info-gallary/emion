"""
EmION — Authentic ION-DTN Framework.
All operations use real ION C-engine + pyion. No dummies.
"""

__version__ = "0.3.0"
__author__ = "EmION Team"

from .core.node import EmionNode
from .core.engine import EmionEngine
from .plugins.base import APIPlugin

ION_AVAILABLE = True


def dashboard(host="0.0.0.0", port=8420):
    """Launch the EmION web dashboard."""
    from .dashboard.server import run
    run(host=host, port=port)

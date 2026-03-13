"""
EmION Plugins — API-based plugin system.

Users provide their own anomaly detection module as a FastAPI endpoint.
EmION calls the user's API during simulation for each node.

See api_template.py for the expected format.
"""

from .base import EmionPlugin

"""
soul_validator.server — create the FastAPI app programmatically.
Can be used standalone or embedded in a larger service.

Usage:
    from soul_validator.server import create_app
    app = create_app()
"""
import sys
from pathlib import Path

# Allow importing from the project root (rules/, engine/)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

def create_app(rules_dir: str | None = None, rules_version: str = "v1.0.0"):
    """Create and return the FastAPI application."""
    # Import the existing main.py app factory pattern
    from main import app
    return app

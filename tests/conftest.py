"""
Shared pytest fixtures and configuration for endoflife_fetcher tests.
"""

import sys
from pathlib import Path

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

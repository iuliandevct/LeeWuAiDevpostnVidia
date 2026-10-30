"""
scripts/ai_ops_service.py
Backward-compatible proxy module for ai_ops_service.py.
Redirects all imports directly to the authoritative root ai_ops_service implementation.
"""

import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ai_ops_service import *

"""
MPDTE College Predictor & Analyzer
Main entry point
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db
from gui.main_window import main

if __name__ == "__main__":
    init_db()
    main()

#!/usr/bin/env python3
"""
main.py - entry point for EYE_CONTROL_OPTIMIZATION
Launches main_app.py which is the full production system.
"""
import sys
import os

# Ensure the project folder is in path regardless of where python is called from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_app import main

if __name__ == "__main__":
    main()

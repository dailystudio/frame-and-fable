#!/usr/bin/env python3
"""
Model Creator launcher script (forwarding to model_creator.py).
"""
import sys
import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "model_creator.py"
    runpy.run_path(str(target), run_name="__main__")

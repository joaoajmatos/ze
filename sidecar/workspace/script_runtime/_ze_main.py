"""Entry point of a tool script: runs main.py with the scratch dir importable."""

import os
import runpy
import sys

sys.path.insert(0, os.getcwd())
runpy.run_path("main.py", run_name="__main__")

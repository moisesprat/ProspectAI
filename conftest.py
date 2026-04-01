import sys
import os

# Ensure the project root is on sys.path so that top-level modules
# (main, prospect_ai_crew, agents, utils, config) are importable
# even when pytest collects tests inside the `tests/` package.
sys.path.insert(0, os.path.dirname(__file__))

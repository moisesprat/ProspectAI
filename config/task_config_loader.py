"""
Task Configuration Loader
Loads task configurations from tasks.yaml and renders them with runtime variables.
"""

from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

import yaml


class TaskConfigLoader:
    """Loads and renders task configurations from tasks.yaml."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            project_root = Path(__file__).parent.parent
            resolved = project_root / "config" / "tasks.yaml"
        else:
            resolved = Path(config_path)

        self.config_path = resolved
        self.config_data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Task config not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not config or "tasks" not in config:
            raise ValueError("Invalid configuration: missing 'tasks' section")
        return config

    def get_task_config(self, task_key: str) -> Dict[str, Any]:
        tasks = self.config_data["tasks"]
        if task_key not in tasks:
            raise KeyError(f"Task '{task_key}' not found. Available: {list(tasks)}")
        return tasks[task_key]

    def render(self, task_key: str, **kwargs) -> Dict[str, str]:
        """Return description and expected_output with $variables substituted."""
        cfg = self.get_task_config(task_key)
        return {
            "description": Template(cfg["description"]).substitute(**kwargs),
            "expected_output": Template(cfg["expected_output"]).substitute(**kwargs),
        }

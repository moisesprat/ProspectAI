"""
Task Configuration Loader
Loads task configurations from tasks.yaml and renders them with runtime variables.
"""

import json
import types
from pathlib import Path
from string import Template
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union, get_args, get_origin

import yaml
from pydantic import BaseModel

# Template variables a description may use besides sector/today/risk_profile.
_GENERATED_VARS = ("output_example", "allowed_values")


def _unwrap(annotation: Any) -> Any:
    """Strip Annotated and Optional so a field's real type is visible."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _unwrap(args[0]) if len(args) == 1 else annotation
    return annotation


def literal_fields(model: type, prefix: str = "") -> List[Tuple[str, Tuple[Any, ...]]]:
    """(path, allowed values) for every Literal field of `model`, in field order.

    Walks Optional[...], Annotated[...], List[...] and nested models; a list adds
    "[]" to the path, e.g. ``positions[].action``.
    """
    found: List[Tuple[str, Tuple[Any, ...]]] = []
    for name, field in model.model_fields.items():
        path = f"{prefix}{name}"
        annotation = _unwrap(field.annotation)
        is_list = get_origin(annotation) in (list, List)
        if is_list:
            annotation = _unwrap(get_args(annotation)[0])
            path += "[]"
        if get_origin(annotation) is Literal:
            found.append((path, get_args(annotation)))
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            found.extend(literal_fields(annotation, f"{path}."))
    return found


def allowed_values_text(model: type) -> str:
    """One line per Literal field, ``path: "v1" | "v2"``, or ``(none)`` (D-11: exact values in the prompt)."""
    lines = [
        f"{path}: " + " | ".join(json.dumps(v) for v in values)
        for path, values in literal_fields(model)
    ]
    return "\n".join(lines) if lines else "(none)"


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

    def render(self, task_key: str, output_model: Optional[type] = None, **kwargs) -> Dict[str, str]:
        """Return description and expected_output with $variables substituted.

        Besides the runtime variables, a task may use:
          $output_example  the task's ``output_example`` as indented JSON
          $allowed_values  the Literal values of ``output_model`` (when given)
        Each is substituted as one value and never re-templated, so a ``$`` inside
        an example is safe. Using one without its source raises KeyError naming the task.
        """
        cfg = self.get_task_config(task_key)
        variables = dict(kwargs)
        if "output_example" in cfg:
            variables["output_example"] = json.dumps(cfg["output_example"], indent=2)
        if output_model is not None:
            variables["allowed_values"] = allowed_values_text(output_model)
        try:
            return {
                "description": Template(cfg["description"]).substitute(**variables),
                "expected_output": Template(cfg["expected_output"]).substitute(**variables),
            }
        except KeyError as exc:
            if exc.args and exc.args[0] in _GENERATED_VARS:
                raise KeyError(
                    f"Task '{task_key}' uses ${exc.args[0]} but has no "
                    f"{'output_example' if exc.args[0] == 'output_example' else 'output_model'} to fill it"
                ) from None
            raise

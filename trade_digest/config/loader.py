from pathlib import Path

import yaml


def load_settings(path: Path) -> dict:
    """Load settings YAML and validate it is a mapping.

    Raises FileNotFoundError when the file does not exist, or ValueError when the
    YAML is empty or not a mapping. This prevents callers from receiving `None`
    (yaml.safe_load returns None for empty files) and later failing with
    TypeError: 'NoneType' object is not subscriptable.
    """
    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Settings file {path} is empty or malformed: expected YAML mapping")
    return data


def load_holdings(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Holdings file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Holdings file {path} is empty or malformed: expected YAML mapping")
    return data

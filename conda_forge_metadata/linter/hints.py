from __future__ import annotations

import sys
from functools import lru_cache

import requests

if sys.version_info[:2] < (3, 11):
    import tomli as tomllib
else:
    import tomllib


@lru_cache(maxsize=1)
def get_hints() -> dict[str, str]:
    req = requests.get(
        "https://raw.githubusercontent.com/conda-forge/"
        "conda-forge-pinning-feedstock/main/recipe/linter_hints/hints.toml"
    )
    req.raise_for_status()
    hints_toml_str = req.content.decode("utf-8")
    hints_dict = tomllib.loads(hints_toml_str)["hints"]
    return hints_dict

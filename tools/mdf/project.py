"""Load and schema-validate a machine/station project directory."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

from .motion import Axis

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"

FILES = {
    "requirements": "requirements.yaml",
    "params": "params.yaml",
    "cycle": "cycle.yaml",
    "layout": "layout.yaml",
    "tests": "tests.yaml",
}


class ProjectError(Exception):
    pass


@dataclass
class Project:
    root: Path
    data: dict = field(default_factory=dict)
    axes: dict[str, Axis] = field(default_factory=dict)

    def param(self, name: str) -> float:
        try:
            return float(self.data["params"]["params"][name]["value"])
        except KeyError as e:
            raise ProjectError(f"unknown parameter {name!r}") from e

    def num(self, v) -> float:
        """A number, or the name of a parameter."""
        return self.param(v) if isinstance(v, str) else float(v)

    @property
    def speeds(self) -> list[tuple[str, float]]:
        p = self.data["params"]["params"]
        return [(k, float(p[k]["value"])) for k in ("speed_min_cph", "speed_nom_cph", "speed_max_cph")]

    @property
    def layout(self) -> dict:
        return self.data["layout"]

    @property
    def cycle(self) -> dict:
        return self.data["cycle"]


def load(root: str | Path) -> Project:
    root = Path(root)
    proj = Project(root=root)
    for key, fname in FILES.items():
        path = root / fname
        if not path.exists():
            raise ProjectError(f"missing {fname} in {root}")
        with path.open() as fh:
            doc = yaml.safe_load(fh)
        schema_path = SCHEMA_DIR / f"{key}.schema.json"
        schema = json.loads(schema_path.read_text())
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as e:
            loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
            raise ProjectError(f"{fname}: schema error at {loc}: {e.message}") from e
        proj.data[key] = doc
    for axis_id, spec in proj.cycle["axes"].items():
        proj.axes[axis_id] = Axis(axis_id, spec)
    return proj

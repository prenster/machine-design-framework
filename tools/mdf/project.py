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
OPTIONAL = {
    "bom": "bom.yaml",
    "constraints": "constraints.yaml",
    "io_list": "io_list.yaml",
    "assembly3d": "assembly3d.yaml",
    "sil": "sil.yaml",
    "stacks": "stacks.yaml",
    "safety": "safety.yaml",
    "fmea": "fmea.yaml",
    "acceptances": "acceptances.yaml",
    "interfaces": "interfaces.yaml",
}


class ProjectError(Exception):
    pass


@dataclass
class Project:
    root: Path
    variant: str | None = None
    raw: dict = field(default_factory=dict)   # files as written (before variant overrides and expressions)
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


def _substitute(node, ns):
    """Strings beginning with '=' are expressions over parameter names, e.g. '=sheet_length_mm + 2'."""
    if isinstance(node, dict):
        return {k: _substitute(v, ns) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, ns) for v in node]
    if isinstance(node, str) and node.startswith("="):
        import ast
        from .bom import _eval
        try:
            return _eval(ast.parse(node[1:].strip(), mode="eval"), ns)
        except Exception as e:  # noqa: BLE001
            raise ProjectError(f"cannot evaluate expression {node!r}: {e}") from e
    return node


def variants(root: str | Path) -> list[str]:
    with (Path(root) / "params.yaml").open() as fh:
        doc = yaml.safe_load(fh)
    return list((doc.get("variants") or {}).keys())


def load(root: str | Path, variant: str | None = None) -> Project:
    root = Path(root)
    proj = Project(root=root)
    proj.variant = variant
    ns = None
    for key, fname in list(FILES.items()) + list(OPTIONAL.items()):
        path = root / fname
        if not path.exists():
            if key in OPTIONAL:
                continue
            raise ProjectError(f"missing {fname} in {root}")
        with path.open() as fh:
            doc = yaml.safe_load(fh)
        import copy
        proj.raw[key] = copy.deepcopy(doc)
        if key == "params":
            vs = doc.get("variants") or {}
            if variant is not None:
                if variant not in vs:
                    raise ProjectError(f"unknown variant {variant!r}; params.yaml defines {list(vs)}")
                for name, val in vs[variant].items():
                    if name not in doc["params"]:
                        raise ProjectError(f"variant {variant} overrides unknown param {name}")
                    doc["params"][name] = {**doc["params"][name], "value": val}
            ns = {k: v["value"] for k, v in doc["params"].items()}
        elif ns is not None:
            doc = _substitute(doc, ns)
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

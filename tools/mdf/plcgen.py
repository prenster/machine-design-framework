"""Generate PLC global variable lists from the source-of-truth YAML files.

GVL_Cycle.st  <- cycle.yaml   (valve on/off angles, sensor check angles, park angle)
GVL_IO.st     <- io_list.yaml (I/O tags and types)

Each generated file carries the sha256 of its source; PLC-GEN fails when they are stale, so the PLC
can never silently disagree with the cycle diagram.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .project import Project

TYPES = {"BOOL": "BOOL", "INT": "INT", "REAL": "REAL"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def gvl_cycle(proj: Project) -> str:
    c = proj.cycle
    lines = [f"(* GENERATED from cycle.yaml - DO NOT EDIT. source-hash: {_hash(proj.root / 'cycle.yaml')} *)",
             "(* Commanded angles (deg). Effective timing = commanded + device delay; see GLUE-BEAD/PROD-* checks. *)",
             "VAR_GLOBAL CONSTANT"]
    for vid, v in c["valves"].items():
        n = vid.upper()
        lines.append(f"    {n}_ON  : REAL := {float(v['on']):.4f};")
        lines.append(f"    {n}_OFF : REAL := {float(v['off']):.4f};")
    for sid, s in c.get("sensors", {}).items():
        lines.append(f"    {sid.upper()}_CHECK : REAL := {float(s['check_at']):.4f};")
    for aid, a in c["axes"].items():
        sup = a.get("superimposed")
        if sup:
            n = aid.upper()
            lines.append(f"    {n}_OFFSET_MIN : REAL := {float(sup['range'][0]):.4f};   (* per-cycle offset range, mm *)")
            lines.append(f"    {n}_OFFSET_MAX : REAL := {float(sup['range'][1]):.4f};")
    if "park_angle" in c:
        lines.append(f"    PARK_ANGLE : REAL := {float(c['park_angle']):.4f};")
    lines.append("END_VAR")
    return "\n".join(lines) + "\n"


def gvl_io(proj: Project) -> str:
    lines = [f"(* GENERATED from io_list.yaml - DO NOT EDIT. source-hash: {_hash(proj.root / 'io_list.yaml')} *)",
             "VAR_GLOBAL"]
    for s in proj.data["io_list"]["signals"]:
        where = "virtual" if s.get("virtual") else f"{s['card']}.{s['ch']} {s['device']}"
        lines.append(f"    {s['tag']} : {TYPES[s['type']]};   (* {s['dir']}  {where} *)")
    lines.append("END_VAR")
    return "\n".join(lines) + "\n"


def targets(proj: Project) -> dict[Path, str]:
    gen = proj.root / "plc" / "generated"
    out = {gen / "GVL_Cycle.st": gvl_cycle(proj)}
    if "io_list" in proj.data:
        out[gen / "GVL_IO.st"] = gvl_io(proj)
    return out


def write(proj: Project) -> list[Path]:
    written = []
    for path, text in targets(proj).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(path)
    return written


def stale(proj: Project) -> list[str]:
    issues = []
    for path, text in targets(proj).items():
        if not path.exists():
            issues.append(f"{path.relative_to(proj.root)} missing - run `make plc P={proj.root}`")
        elif path.read_text() != text:
            issues.append(f"{path.relative_to(proj.root)} is stale vs. its YAML source - run `make plc P={proj.root}`")
    return issues

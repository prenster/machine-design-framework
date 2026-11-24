"""Actuation policy: prefer mechanical cams, then servos, then pneumatics (configurable per project).

Any axis or actuating valve below the top preference must carry an `actuation_reason`. The reasons are
listed in every report so the chief engineer reviews them. Rationale and when pneumatics are the right
answer: docs/ACTUATION.md.
"""
from __future__ import annotations

from .checks import FAIL, PASS, CheckResult

DEFAULT = ["mechanical_cam", "servo", "pneumatic"]
VALVE_ACTUATOR_KINDS = {"pneumatic_actuator"}


def check_actuation(proj) -> list[CheckResult]:
    pref = proj.cycle.get("actuation_preference", DEFAULT)
    issues, lines = [], []
    for aid, a in proj.cycle["axes"].items():
        t = a["type"]
        rank = pref.index(t) if t in pref else len(pref)
        if rank > 0:
            r = a.get("actuation_reason")
            if not r:
                issues.append(f"axis {aid} is {t}, preference is {pref[0]}: add actuation_reason")
            else:
                lines.append(f"axis {aid} ({t}): {r}")
        else:
            lines.append(f"axis {aid} ({t}): preferred actuation")
    for vid, v in proj.cycle["valves"].items():
        if v.get("kind") in VALVE_ACTUATOR_KINDS:
            r = v.get("actuation_reason")
            if not r:
                issues.append(f"valve {vid} drives a pneumatic actuator: add actuation_reason")
            else:
                lines.append(f"valve {vid} (pneumatic actuator): {r}")
    return [CheckResult("ACT-POLICY", FAIL if issues else PASS,
                        f"actuation preference {' > '.join(pref)}; {len(lines)} choices reviewed", issues + lines)]

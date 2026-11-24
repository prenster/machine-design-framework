"""Integrity: the claim contract and the check lock.

Claim contract (from "Done Is Not Correct", arXiv 2611.10063): a completion claim must sit *after* a
measurement of the final state. `mdf verify` writes build/verify.json with a hash of every input file;
`mdf claimcheck` (pre-commit hook, CI) refuses when that verify is stale or failed.

Check lock (from FunCAD-Harness: "checks lost during repair"): every value that defines what a check
demands - clearances and contact windows, port tolerances, glue spec, requirement text and verification
links, SIL expectations, constraints, requirement-sourced params, stack targets, safety PLr - is hashed
per section into checks.lock. If any changes, verify FAILS (CHECK-LOCK) until the chief engineer reviews
and runs `make lock`. An agent can still change a check; it cannot do so silently.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import yaml

from .checks import FAIL, PASS, WARN, CheckResult

INPUT_GLOBS = ["*.yaml", "cad/**/*.py", "plc/**/*.st"]


def inputs_hash(root: Path) -> str:
    h = hashlib.sha256()
    files = sorted({f for g in INPUT_GLOBS for f in root.glob(g) if "build" not in f.parts})
    for f in files:
        if f.name == "checks.lock":
            continue
        h.update(str(f.relative_to(root)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def write_verify_record(root: Path, out: Path, verdict: str, results) -> Path:
    rec = {"inputs_sha256": inputs_hash(root), "verdict": verdict,
           "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "checks": {s: sum(1 for r in results if r.status == s) for s in (PASS, WARN, FAIL)}}
    path = out / "verify.json"
    path.write_text(json.dumps(rec, indent=2))
    return path


def claimcheck(root: Path) -> tuple[bool, str]:
    rec_path = root / "build" / "verify.json"
    if not rec_path.exists():
        return False, f"{root}: never verified - run `make verify P={root}`"
    rec = json.loads(rec_path.read_text())
    if rec["inputs_sha256"] != inputs_hash(root):
        return False, f"{root}: inputs changed since the last verify ({rec['time_utc']}) - re-run verify before claiming"
    expect_fail = (root / ".mdf-expect-fail").exists()
    if rec["verdict"] == FAIL and not expect_fail:
        return False, f"{root}: last verify FAILED - fix the design before committing"
    return True, f"{root}: verify {rec['verdict']} on current inputs ({rec['time_utc']})"


# ----------------------------------------------------------------- check lock
def _sections(proj) -> dict:
    d = proj.data
    lay = d["layout"]
    sec = {
        "layout.clearance": lay.get("clearance"),
        "layout.ports": lay.get("ports"),
        "layout.glue.spec": {k: v for k, v in (lay.get("glue") or {}).items() if k in ("bead", "gap")},
        "requirements": [{k: r[k] for k in ("id", "text", "verification")} for r in d["requirements"]["requirements"]],
        "params.requirement": {k: v["value"] for k, v in d["params"]["params"].items() if v.get("source") == "requirement"},
        "sil.expectations": [{"id": s["id"], "speeds": s.get("speeds"), "cycles": s["cycles"],
                              "inject": s.get("inject"), "expect": s["expect"]}
                             for s in d.get("sil", {}).get("scenarios", [])],
        "constraints": d.get("constraints", {}).get("constraints"),
        "stacks.targets": [{"id": s["id"], "target": s["target"]} for s in d.get("stacks", {}).get("stacks", [])],
        "safety.plr": [{"id": h["id"], "S": h.get("S"), "F": h.get("F"), "P": h.get("P")}
                       for h in d.get("safety", {}).get("hazards", [])],
        "cam.limits": {aid: (a.get("cam") or {}).get("limits") for aid, a in proj.cycle["axes"].items() if a.get("cam")},
        "cad.expectations": [{"id": b["id"], "expect": b.get("expect")} for b in d.get("assembly3d", {}).get("bodies", [])
                             if b.get("expect")],
    }
    return {k: hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:16]
            for k, v in sec.items()}


def write_lock(proj) -> Path:
    path = proj.root / "checks.lock"
    body = {"_note": "Hashes of everything that defines what the checks demand. Regenerate ONLY after the "
                     "chief engineer approves a change to a check (`make lock P=...`), and say so in the commit.",
            "sections": _sections(proj)}
    path.write_text(yaml.safe_dump(body, sort_keys=True))
    return path


def check_lock(proj) -> list[CheckResult]:
    path = proj.root / "checks.lock"
    if not path.exists():
        return [CheckResult("CHECK-LOCK", WARN, "no checks.lock: check definitions are not protected",
                            ["run `make lock P=<project>` once the checks are approved"])]
    locked = yaml.safe_load(path.read_text()).get("sections", {})
    now = _sections(proj)
    changed = [k for k in sorted(set(locked) | set(now)) if locked.get(k) != now.get(k)]
    if changed:
        return [CheckResult("CHECK-LOCK", FAIL, f"{len(changed)} check-defining sections changed since approval",
                            [f"changed: {c}" for c in changed] +
                            ["if this was a design fix, restore the check; if the check itself must change, "
                             "the chief engineer reviews the diff and runs `make lock`, noted in the commit"])]
    return [CheckResult("CHECK-LOCK", PASS, f"{len(now)} check-defining sections match the approved lock")]

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
def _raw_sections(proj) -> dict:
    """Check definitions as written (expressions unevaluated, no variant overrides): one lock for all variants."""
    d = {k: v for k, v in proj.raw.items()} if proj.raw else proj.data
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
        "cam.limits": {aid: (a.get("cam") or {}).get("limits") for aid, a in d["cycle"]["axes"].items() if a.get("cam")},
        "cad.expectations": [{"id": b["id"], "expect": b.get("expect")} for b in d.get("assembly3d", {}).get("bodies", [])
                             if b.get("expect")],
        "acceptances": d.get("acceptances", {}).get("accepted"),
        "interfaces.timing": [{k: s.get(k) for k in ("id", "available_at_deg", "needed_by_deg", "latency_ms")}
                              for s in d.get("interfaces", {}).get("signals", [])],
        "variants": d["params"].get("variants"),
    }
    return json.loads(json.dumps(sec, default=str))


def _hash(v) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _sections(proj) -> dict:
    return {k: _hash(v) for k, v in _raw_sections(proj).items()}


TITLES = {
    "layout.clearance": "Clearances and allowed contacts (mm, machine-angle windows)",
    "layout.ports": "Where the product must be picked and placed, and how precisely",
    "layout.glue.spec": "Glue bead position and nozzle gap",
    "requirements": "Requirements and how each is verified",
    "params.requirement": "Numbers set by requirement (speeds, margins, limits)",
    "sil.expectations": "What each PLC simulation scenario must show",
    "constraints": "Cross-spec rules",
    "stacks.targets": "Tolerance stack targets",
    "safety.plr": "Hazard risk-graph inputs (S/F/P)",
    "cam.limits": "Cam design limits",
    "cad.expectations": "Geometry the CAD must measure to",
    "acceptances": "Results the chief engineer has accepted",
    "interfaces.timing": "Host-machine signal timing budget",
    "variants": "Product size variants every check runs for",
}


def _diff(a, b, path="", out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _diff(a.get(k), b.get(k), f"{path}.{k}" if path else str(k), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append(f"{path}: {json.dumps(a, default=str)[:120]} -> {json.dumps(b, default=str)[:120]}")
    return out


def readable(proj) -> str:
    raw = _raw_sections(proj)
    lines = [f"# Check definitions: {proj.root.name}", "",
             "Everything the automated checks demand of the design. Read it as a list of promises:",
             "if something here is wrong or too loose, say so. Approving = the chief engineer runs `make lock`.",
             "After approval, any change to these values makes verify FAIL until approved again.", ""]
    for k, v in raw.items():
        if v in (None, [], {}):
            continue
        lines += [f"## {TITLES.get(k, k)}", "", "```yaml", yaml.safe_dump(v, sort_keys=False, width=110, default_flow_style=None).rstrip(), "```", ""]
    return "\n".join(lines)


def write_lock(proj, approved_by: str | None = None) -> Path:
    """approved_by=None writes an UNREVIEWED baseline (what Claude may write): it still detects later changes,
    but CHECK-LOCK reports that no human has approved the definitions. Only a person passes approved_by."""
    path = proj.root / "checks.lock"
    raw = _raw_sections(proj)
    body = {"_note": "Everything that defines what the checks demand. Approval = the chief engineer runs "
                     "`make lock P=... BY=\"name\"` after reading CHECKS.md. A lock without approved_by "
                     "is an unreviewed baseline.",
            "approved_by": approved_by,
            "approved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if approved_by else None,
            "sections": {k: _hash(v) for k, v in raw.items()},
            "values": raw}
    path.write_text(yaml.safe_dump(body, sort_keys=True, width=110))
    (proj.root / "CHECKS.md").write_text(readable(proj))
    return path


def check_lock(proj) -> list[CheckResult]:
    path = proj.root / "checks.lock"
    if not path.exists():
        return [CheckResult("CHECK-LOCK", WARN, "no checks.lock: check definitions are not protected",
                            ["run `make lock P=<project>` once the checks are approved"])]
    lock = yaml.safe_load(path.read_text())
    locked = lock.get("sections", {})
    old_vals = lock.get("values", {})
    raw = _raw_sections(proj)
    now = {k: _hash(v) for k, v in raw.items()}
    empty = {_hash(None), _hash([]), _hash({})}
    changed = [k for k in sorted(set(locked) | set(now))
               if locked.get(k) != now.get(k) and not (k not in locked and now.get(k) in empty)]
    if changed:
        det = []
        for c in changed:
            det.append(f"changed: {TITLES.get(c, c)} [{c}]")
            if c in old_vals:
                det += ["    " + x for x in _diff(old_vals.get(c), raw.get(c))[:12]]
        return [CheckResult("CHECK-LOCK", FAIL, f"{len(changed)} check-defining sections changed since approval",
                            det +
                            ["if this was a design fix, restore the check; if the check itself must change, "
                             "the chief engineer reviews the diff and runs `make lock`, noted in the commit"])]
    if not lock.get("approved_by"):
        return [CheckResult("CHECK-LOCK", WARN, f"{len(now)} sections match an UNREVIEWED baseline lock",
                            ["no person has approved these check definitions yet: read CHECKS.md, then "
                             "`make lock P=<project> BY=\"<name>\"`"])]
    return [CheckResult("CHECK-LOCK", PASS, f"{len(now)} check-defining sections match the lock approved by "
                                            f"{lock['approved_by']} ({lock.get('approved_utc')})")]

"""Risk assessment (ISO 12100 / ISO 13849-1 risk graph) and FMEA structure checks.

These checks keep the safety and reliability *bookkeeping* honest. They do not make a machine safe:
the achieved Performance Level must be calculated (e.g. SISTEMA) and validated by a qualified person.

SAFETY
  - PLr per hazard from the ISO 13849-1 risk graph (S severity, F frequency/exposure, P avoidability):
      S1F1P1 a | S1F1P2 b | S1F2P1 b | S1F2P2 c | S2F1P1 c | S2F1P2 d | S2F2P1 d | S2F2P2 e
    (ISO 13849-1:2023 allows lowering by one level for low probability of occurrence; not applied here.)
  - every hazard has a mitigation; PLr >= c needs a guard or safety function, not just information
  - every safety function: required PL >= the highest PLr that relies on it; design PL claimed >= required;
    devices exist in the BOM and are safety-rated; validated by at least one SIL scenario that exists
FMEA
  - RPN = S x O x D; S >= 9 or RPN >= threshold must carry an action; detection references must exist
"""
from __future__ import annotations

from .checks import FAIL, PASS, WARN, CheckResult

GRAPH = {("S1", "F1", "P1"): "a", ("S1", "F1", "P2"): "b", ("S1", "F2", "P1"): "b", ("S1", "F2", "P2"): "c",
         ("S2", "F1", "P1"): "c", ("S2", "F1", "P2"): "d", ("S2", "F2", "P1"): "d", ("S2", "F2", "P2"): "e"}
ORDER = "abcde"


def check_safety(proj) -> list[CheckResult]:
    sf = proj.data.get("safety")
    if not sf:
        return []
    parts = {p["id"]: p for p in proj.data.get("bom", {}).get("parts", [])}
    scen = {s["id"] for s in proj.data.get("sil", {}).get("scenarios", [])}
    funcs = {f["id"]: f for f in sf.get("safety_functions", [])}
    issues, lines = [], []
    need: dict[str, str] = {}
    for h in sf["hazards"]:
        plr = GRAPH.get((h["S"], h["F"], h["P"]))
        if plr is None:
            issues.append(f"{h['id']}: invalid risk graph inputs {h['S']}/{h['F']}/{h['P']}")
            continue
        mits = h.get("mitigations", [])
        kinds = {m["type"] for m in mits}
        lines.append(f"{h['id']} {h['hazard']}: PLr {plr} ({h['S']}{h['F']}{h['P']}); mitigations: "
                     f"{', '.join(m.get('ref') or m['type'] for m in mits) or 'NONE'}")
        if not mits:
            issues.append(f"{h['id']}: no mitigation")
        if ORDER.index(plr) >= 2 and not kinds & {"guard", "safety_function", "inherent"}:
            issues.append(f"{h['id']}: PLr {plr} mitigated only by information for use")
        for m in mits:
            if m["type"] == "safety_function":
                if m.get("ref") not in funcs:
                    issues.append(f"{h['id']}: safety function {m.get('ref')} not defined")
                else:
                    cur = need.get(m["ref"], "a")
                    need[m["ref"]] = max(cur, plr, key=ORDER.index)
    for fid, f in funcs.items():
        req = need.get(fid)
        if req is None:
            lines.append(f"{fid}: not referenced by any hazard")
            continue
        claim = f.get("pl_design")
        if claim is None:
            issues.append(f"{fid}: requires PL {req}; no design PL stated")
        elif ORDER.index(claim) < ORDER.index(req):
            issues.append(f"{fid}: design PL {claim} below required PL {req}")
        else:
            lines.append(f"{fid}: requires PL {req}, design claims PL {claim} (to be validated, e.g. SISTEMA)")
        for d in f.get("devices", []):
            p = parts.get(d)
            if p is None:
                issues.append(f"{fid}: device {d} not in BOM")
                continue
            sr = p.get("specs", {}).get("safety_rated")
            if not (sr["value"] if isinstance(sr, dict) else sr):
                issues.append(f"{fid}: device {d} is not safety-rated")
        vals = f.get("validated_by", [])
        if not vals:
            issues.append(f"{fid}: no SIL scenario validates the reaction")
        for v in vals:
            if v not in scen:
                issues.append(f"{fid}: validation scenario {v} does not exist in sil.yaml")
    lines.append("Bookkeeping only: achieved PL and validation need a qualified person (ISO 13849-2).")
    return [CheckResult("SAFETY", FAIL if issues else PASS,
                        f"{len(sf['hazards'])} hazards, {len(funcs)} safety functions", issues + lines)]


def check_fmea(proj, known_ids: set[str]) -> list[CheckResult]:
    fm = proj.data.get("fmea")
    if not fm:
        return []
    thr = int(fm.get("rpn_action_threshold", 100))
    tests = {t["id"] for t in proj.data["tests"]["tests"]}
    issues, warns, lines = [], [], []
    rows = []
    for it in fm["items"]:
        rpn = it["S"] * it["O"] * it["D"]
        rows.append((rpn, it))
        for ref in it.get("detection", []):
            if ref not in known_ids and ref not in tests:
                issues.append(f"{it['id']}: detection reference {ref} is not a check, scenario or test")
        if (it["S"] >= 9 or rpn >= thr) and not it.get("action"):
            issues.append(f"{it['id']} {it['failure_mode']}: RPN {rpn} (S{it['S']} O{it['O']} D{it['D']}) needs an action")
    for rpn, it in sorted(rows, key=lambda r: -r[0]):
        tag = f" -> action: {it['action']}" if it.get("action") else ""
        lines.append(f"RPN {rpn:3d}  {it['id']} {it['item']}: {it['failure_mode']}{tag}")
    return [CheckResult("FMEA", FAIL if issues else (WARN if warns else PASS),
                        f"{len(rows)} failure modes, action threshold RPN {thr}", issues + warns + lines)]

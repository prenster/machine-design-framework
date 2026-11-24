"""Human-action queue and fidelity ladder.

The framework degrades gracefully: every part and number carries how good it is, and anything not good
enough for the next gate becomes an action for a human: DOWNLOAD a vendor STEP, LOOK UP a datasheet,
TEST to replace an assumption, REVIEW, or QUOTE. Criticality decides urgency: an envelope within a few
mm of another body needs real geometry before detailed design; one with lots of room can wait.

Fidelity ladder
  specs:     estimate  ->  datasheet (with evidence url)  ->  measured
  geometry:  estimate  ->  datasheet_envelope  ->  vendor_step  ->  measured
  params:    assumed   ->  datasheet / requirement / derived  ->  measured

Gates (docs/WORKFLOW.md): G1 concept, G2 functional models, G3 detailed design, G4 release for manufacture.
`mdf verify --gate G3` turns every action that blocks G3 or earlier into a FAIL.
"""
from __future__ import annotations

from dataclasses import dataclass

from .project import Project

GATES = ["G1", "G2", "G3", "G4", "G5"]
SPEC_RANK = {"estimate": 0, "datasheet": 1, "measured": 2}
GEO_RANK = {"estimate": 0, "datasheet_envelope": 1, "vendor_step": 2, "measured": 3}


@dataclass
class Action:
    kind: str          # DOWNLOAD | LOOKUP | TEST | REVIEW | QUOTE | REGEN
    item: str
    why: str
    blocks: str        # gate this blocks
    effort: str = ""
    priority: int = 2  # 1 high .. 3 low

    def blocks_by(self, gate: str) -> bool:
        return GATES.index(self.blocks) <= GATES.index(gate)


def _critical_parts(proj: Project, results) -> dict[str, float]:
    """part id -> tightest 3D clearance margin (mm) of any body made from it."""
    a3 = proj.data.get("assembly3d")
    if not a3:
        return {}
    part_of = {b["id"]: b.get("part") for b in a3["bodies"]}
    out: dict[str, float] = {}
    for r in results:
        if r.check_id != "SWEEP-3D":
            continue
        for (a, b), margin in r.data.get("worst", {}).items():
            for body in (a, b):
                pid = part_of.get(body)
                if pid:
                    out[pid] = min(out.get(pid, 1e9), margin)
    return out


def build(proj: Project, results) -> list[Action]:
    acts: list[Action] = []
    pp = proj.data["params"]["params"]
    crit_mm = float(pp.get("fidelity_critical_margin_mm", {}).get("value", 5.0))
    margins = _critical_parts(proj, results)
    bom = proj.data.get("bom", {}).get("parts", [])
    a3 = proj.data.get("assembly3d")
    geo_parts = {b.get("part") for b in a3["bodies"] if b.get("part")} if a3 else set()
    for part in bom:
        pid = part["id"]
        fid = part.get("fidelity", {})
        spec_f = fid.get("specs", "estimate")
        geo_f = fid.get("geometry", "estimate")
        catalog = part["source"] in ("catalog", "example")
        if catalog and SPEC_RANK[spec_f] < 1 and part.get("specs"):
            acts.append(Action("LOOKUP", pid, f"specs are '{spec_f}': {part['description']}. Choose a catalog part, "
                                              f"copy datasheet specs, add evidence url", "G3", "15-30 min", 1))
        if part.get("unverified"):
            acts.append(Action("LOOKUP", pid, f"specs still estimated: {', '.join(part['unverified'])}"
                                              f" ({part.get('part_number', part['description'])})", "G3", "10 min", 2))
        if catalog and not part.get("part_number"):
            acts.append(Action("QUOTE", pid, "no vendor part number: cannot get 3 quotes / PO", "G4", "after LOOKUP", 3))
        if pid in geo_parts:
            m = margins.get(pid, float("inf"))
            if catalog and GEO_RANK[geo_f] < 2:
                if m < crit_mm:
                    acts.append(Action("DOWNLOAD", pid, f"geometry is '{geo_f}' but tightest clearance is {m:+.2f} mm "
                                                         f"(< {crit_mm} mm): needs vendor STEP for a trustworthy 3D check",
                                       "G3", "5 min (vendor configurator)", 1))
                else:
                    mtxt = f"{m:.1f} mm" if m != float("inf") else "> 3 mm from everything"
                    acts.append(Action("DOWNLOAD", pid, f"geometry is '{geo_f}', clearance margin {mtxt}: "
                                                         f"envelope is fine for now, vendor STEP before drawings",
                                       "G4", "5 min", 3))
            if not catalog and GEO_RANK[geo_f] < 1 and m < crit_mm:
                acts.append(Action("REVIEW", pid, f"custom part, tightest clearance {m:+.2f} mm: detail it in CAD "
                                                   f"before trusting the 3D check", "G3", "", 2))
    tests = {t["id"]: t for t in proj.data["tests"]["tests"]}
    for name, p in pp.items():
        if p.get("source") == "assumed":
            t = tests.get(p.get("calibrated_by"), {})
            if t.get("status") != "done":
                acts.append(Action("TEST", f"{p.get('calibrated_by')} -> {name}",
                                   f"verdicts depend on assumed {name} = {p['value']} {p.get('unit', '')}",
                                   "G2", f"${t.get('est_cost_usd', '?')}", 1))
        if p.get("source") == "datasheet" and not (p.get("from_part") or p.get("url")):
            acts.append(Action("LOOKUP", name, "'datasheet' value without from_part or url", "G3", "5 min", 2))
    for t in tests.values():
        if t.get("holdout") and t.get("status") != "done":
            acts.append(Action("TEST", t["id"], f"holdout prediction check: {t['title']}", "G2",
                               f"${t.get('est_cost_usd', '?')}", 2))
        elif not t.get("calibrates") and t.get("status") != "done":
            acts.append(Action("TEST", t["id"], t["title"], "G2", f"${t.get('est_cost_usd', '?')}", 2))
    for req in proj.data["requirements"]["requirements"]:
        if req["verification"]["method"] == "review":
            acts.append(Action("REVIEW", req["id"], req["text"], "G3", "chief engineer", 2))
    for r in results:
        if r.check_id == "PLC-GEN" and r.status != "PASS":
            acts.append(Action("REGEN", "plc/generated", "run `make plc` and commit", "G1", "1 min", 1))
    seen, uniq = set(), []
    for a in sorted(acts, key=lambda a: (a.priority, GATES.index(a.blocks), a.kind, a.item)):
        if (a.kind, a.item) not in seen:
            seen.add((a.kind, a.item))
            uniq.append(a)
    return uniq


def fidelity_summary(proj: Project) -> list[str]:
    bom = proj.data.get("bom", {}).get("parts", [])
    if not bom:
        return []
    spec = {k: 0 for k in SPEC_RANK}
    geo = {k: 0 for k in GEO_RANK}
    for p in bom:
        f = p.get("fidelity", {})
        if p.get("specs"):
            spec[f.get("specs", "estimate")] += 1
        geo[f.get("geometry", "estimate")] += 1
    return [f"specs:    " + ", ".join(f"{k} {v}" for k, v in spec.items()),
            f"geometry: " + ", ".join(f"{k} {v}" for k, v in geo.items())]

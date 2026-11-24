# Workflow: phases, gates and the working session

Loosely follows the VDI 2206 mechatronics V-model and VDI 2221 design method used by European
machine builders, scaled to a single chief engineer working with Claude.

## Phases and gates

| Phase | Output | Tier | Gate (human decides) |
|---|---|---|---|
| **0. Intake + Process** | Spec intake (skill `mdf-intake`, `templates/SPEC_CHECKLIST.md`): sourced, quantified requirements and open questions. Then product states, ports, tolerances; stock and adhesive range; target speed range; cheap coupon tests on real stock (friction, stiffness, glue open time) | A | **G0**: Process approved. Requirements frozen enough to design against |
| **1. Concept** | Station breakdown; mechanism choice per station; first cycle diagram; planar layout; `make verify` passing on the planar model; list of assumed parameters and their tests | A | **G1**: Concept approved. Cycle diagram is now the master |
| **2. Functional models** | Cheap rigs proving each risky physical effect; calibrated params; holdout prediction checked | A design / B build docs | **G2**: Sim trusted for the regimes tested; risky effects proven |
| **3. Detailed design** | 3D code-CAD, catalog selection, BOM, tolerance stacks, I/O list, schematics, PLC code, SIL (soft-PLC against sim), risk assessment | B build / A review | **G3**: Design review (gate-reviewer + human). Release for quotes |
| **4. Manufacture & build** | Machinist drawings, purchase list (3 quotes/line), panel build package, assembly procedure | B | **G4**: Drawings signed by chief engineer before any cutting |
| **5. Commissioning** | Commissioning procedure, measured vs. predicted report, updated params, as-built repo | A analysis / B docs | **G5**: Acceptance against requirements |

What each gate requires of input fidelity is in `docs/FIDELITY.md`; enforce it with `--gate`.
Every gate runs the `gate-reviewer` subagent (TIER-A) first. The reviewer reports. Only the human passes the gate.

## Pilot first

Before the real machine, run the whole pipeline on **one station** end to end:
requirements → cycle → layout/CAD → PLC → verify → physical mock-up → calibration → holdout.
The goal is to prove the pipeline, not the machine. `examples/pick-glue-place` is the template.

## A working session

1. **Human states the goal**: "design the glue station; bead 4 mm ±0.5; 1,500–3,000 cph".
2. **Claude checks the tier**, prints the banner if needed, reads the project, runs `make verify`.
3. **Claude asks only what it can't know**: stocks, adhesive, current machine behaviour, constraints on the floor.
4. **Claude drafts or changes the files** (requirements → process/ports → cycle → layout/CAD → params/tests).
5. **`make verify` until no FAIL.** Fix the design, never the check. Three failed attempts on TIER-B → escalate to TIER-A.
6. **Claude reports**:
   - the verdict
   - decisions needing review
   - physical tests owed, with cost
   - what the checks do **not** cover.
7. **Human reviews**, runs tests, feeds measurements back (`params.yaml`: `source: measured`; `tests.yaml`: `status: done`).
8. **Claude recalibrates and re-verifies.** Holdout tests compare prediction vs. measurement.
9. **Commit.** Message states what changed and the verify verdict.

## Repo layout for a real machine

```
machines/<machine>/
  machine.yaml                 # stations, master angle, speed range, shared params
  stations/<station>/          # same file set as examples/pick-glue-place
    requirements.yaml  cycle.yaml  layout.yaml  params.yaml  tests.yaml
    cad/                       # build123d sources -> STEP (phase 3)
    plc/                       # generated cam tables + IEC 61131-3 ST
  electrical/  io_list.yaml  schematics/
  safety/      risk_assessment.yaml
  bom/         (generated)
  drawings/    (generated, released only at G4)
```

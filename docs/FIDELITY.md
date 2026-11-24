# Fidelity: graceful degradation from "found online" to "measured"

The framework never pretends an input is better than it is. Every part and every number carries its
fidelity. Anything not good enough for the next gate becomes a **human action**: download, look up, test,
review, quote. `make verify` prints the queue and writes it into the report.

## The ladders

| What | Rungs (low → high) | Evidence required |
|---|---|---|
| Part specs (`bom.yaml`) | `estimate` → `datasheet` → `measured` | `datasheet` needs an `evidence` url. Keys still guessed on a datasheet part are listed in `unverified` |
| Part geometry | `estimate` → `datasheet_envelope` → `vendor_step` → `measured` | `vendor_step` needs the file in `cad/vendor/` |
| Parameters (`params.yaml`) | `assumed` → `datasheet` / `requirement` / `derived` → `measured` | `assumed` names its test; `datasheet` names `from_part` or a url |

## How the checks treat each rung

- A **mismatch** between known values is always a FAIL (12 mm shaft into a 14 mm bore).
- A value that is **not known** is never guessed into a PASS. It is reported as `NOT VERIFIED` (WARN)
  and becomes a LOOKUP action. The verdict reads WARN, not PASS, until someone looks it up.
- **Assumptions are guarded against datasheets.** Constraints such as `C-GLUE-ASSUME-ON` fail if the
  simulation assumes a faster valve, a quicker vacuum or a stronger motor than the part in the BOM.
  This caught the example's original 15 ms vacuum assumption: the Schmalz evacuation table says
  15 ml takes 15 ms just to reach 400 mbar, before the valve has even opened.

## Criticality decides urgency

Geometry fidelity only matters where things are close. From the 3D sweep, the framework knows each part's
tightest clearance anywhere in the cycle:

- **margin < 5 mm** (`fidelity_critical_margin_mm`) on an envelope: DOWNLOAD the vendor STEP, priority 1, blocks G3.
- **lots of room**: the envelope is fine; vendor STEP before drawings, priority 3, blocks G4.

So the glue bar that runs 1 mm under the sheet needs real geometry before detailed design; the frame
uprights don't.

## Gates

| Gate | What must be true | Enforce with |
|---|---|---|
| G1 concept | Checks pass on envelopes and estimates; action queue known | `make verify` |
| G2 functional models | Assumed parameters measured (TEST actions done), holdouts compared | `--gate G2` |
| G3 detailed design | All catalog parts at `datasheet` specs; close-clearance parts at `vendor_step`; reviews done | `--gate G3` |
| G4 release | Every catalog part has a part number (quotes), all geometry `vendor_step` or detailed custom CAD | `--gate G4` |

`mdf verify <project> --gate G3` turns every action that blocks G3 or earlier into a FAIL.

## Where things come from, cheapest first

1. **Vendor online datasheets** (Festo, SEW, Schmalz, SMC publish PDFs): Claude looks up, copies, cites.
2. **Vendor sizing tools** (Festo PositioningDrives, SEW Workbench): free, need a human at a GUI. Use
   them where a datasheet number isn't enough (guide moments, exact drive sizing).
3. **Vendor CAD** (configurators, TraceParts, CADENAS): human download, or Claude in Chrome with your login.
4. **Vendor application engineers**: free, slow, authoritative. Good for "does this kit exist".
5. **Physical tests**: the only source for paper, glue, air and real timing.

## Reviewing and approving check definitions

1. Read `<project>/CHECKS.md`: every clearance, tolerance, window, requirement, scenario expectation and limit the
   checks enforce, in plain YAML. Ask "is this the right promise?", not "is this the right syntax?".
2. If it's right: `make lock P=<project> BY="<your name>"`. The lock records you as the approver.
3. Afterwards any change to those values fails verify (CHECK-LOCK) and shows old → new values, until you review and lock again.
4. A lock written by Claude (`make baseline`) is labelled UNREVIEWED and never counts as approval.

## Accepting a warning

A WARN that you judge acceptable (e.g. a tolerance stack that closes statistically but not worst-case) can be
accepted in `acceptances.yaml` (template in `templates/`): which check, who, when, why, and the conditions for
revisiting it. You write it; Claude doesn't. FAILs can't be accepted.

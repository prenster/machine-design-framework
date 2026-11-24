# Verification: what the checks prove, and what they don't

The question this framework exists to answer: **can Claude design a machine without doing stupid
things**, like putting parts where the product isn't, feeding the product to the wrong spot,
gluing air, or timing that only works at one speed?

Answer: Claude by itself, reasoning in its head, **no, not reliably**. Claude writing the design as
data and getting a deterministic verdict on every change: **yes, for everything a check covers.**
The work is making sure the checks cover what matters, and being honest about what they don't.

## Demonstration (in this repo)

`examples/pick-glue-place` passes. `examples/pick-glue-place-broken` contains four plausible mistakes
of the kind made when reasoning about a machine without checking:

| Planted fault | Caught by | What the report says |
|---|---|---|
| Place position typed 594 instead of 600 | PROD-PLACE, SWEEP | registration error −6.1 mm; plate interferes with placed sheet |
| Glue pass at 3 mm height instead of 0 | GLUE-BEAD | gap 4.0 mm; ~50% of the shot lands on the machine |
| Vacuum released early "to save time" | PROD-PLACE | released 7–9 mm above the signature while moving 180–360 mm/s |
| Glue-pass speed changed, neighbours not updated | CYC-LAW | velocity jump at 110° and 150°: infinite acceleration |

While the example was being written, the checker also caught two real errors in the first draft:
the sheet's leading edge hit the signature backstop during the glue pass, and transfer
acceleration at max speed exceeded the sheet-slip limit. Both were fixed in the design, not the check.

## The trust ladder

| Level | What | Status here | Trust |
|---|---|---|---|
| L0 | Schema validation: every file well-formed, every assumption names its test | **implemented** | Total |
| L1 | Cycle laws: coverage, position/velocity continuity, drive limits at max speed | **implemented** | Exact (math) |
| L2 | Planar (side-view) sweep: every moving body vs. every static body at 0.25° steps, all speeds, declared contact windows | **implemented** | Exact for the 2D model. Misses out-of-plane geometry |
| L3 | Product path: pick/carry/place ports, grip timing incl. valve delays, inertial slip, glue bead location and gap, all speeds | **implemented** | Exact given the parameters. **Only as good as the assumed delays and limits** |
| L4 | 3D interference sweep on code-CAD (build123d → mesh, per-angle collision) | roadmap | Exact for geometry |
| L5 | Tolerance stack-ups (worst-case + Monte Carlo) on critical chains | roadmap | Good, if the stacks are chosen correctly (TIER-A + review) |
| L6 | Software-in-the-loop: real PLC code (CODESYS soft-PLC) driving the model over OPC UA/Modbus; fault injection (double sheet, missing sheet, jam, e-stop) | roadmap | Good for logic and timing; not for drive dynamics |
| L7 | Dynamics: Project Chrono (rigid + flexible/FEA bodies): sheet flutter, deflection under load, vibration | roadmap | **Low until calibrated** against physical tests |
| L8 | Physical tests and holdout predictions | process in `tests.yaml` | Ground truth |

## What no check here covers (always state these)

- Sheet behaviour as a flexible body: air under the sheet, flutter at speed, curl, static, grain direction.
- Double-sheet picks, stack separation, ream and humidity variation.
- Adhesive behaviour beyond on/off delay: stringing, spatter, open time, tack development.
- Structural stiffness, fatigue, frame vibration at cycle frequency and harmonics.
- Wear, contamination, maintenance access, operator ergonomics.
- Safety. The risk assessment is a review item, not a check.

Every item here becomes a physical test or a human review, never an assumption that quietly passes.

## Adding a check

1. Write it in `tools/mdf/checks.py` as a deterministic function of the project files.
2. Give it an ID, add it to `ALL_CHECKS`, and reference it from the requirements it verifies.
3. Add a broken example (or a fault in the existing one) that it must catch. A check that has never
   failed has never been tested.

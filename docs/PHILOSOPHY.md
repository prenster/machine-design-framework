# Philosophy

Why the framework is shaped the way it is. The rules in `CLAUDE.md` all come from these principles.

## 1. A machine is a process with hardware around it

Successful special-machine builders (Kolbus, Müller Martini, Horizon, Heidelberg, and the German
*Sondermaschinenbau* tradition generally) start from **what happens to the product**: each state it
passes through, where it is, how it is held, what tolerance it must hit. The machine is whatever
reliably delivers that sequence. So the framework starts every station with product **states and
ports** (pick here, within ±0.3 mm; glue here, 3–7 mm from the edge) before any hardware exists.

## 2. One master: the cycle diagram

In a cam-driven or electronically cammed machine, everything is a function of **machine angle**
(0–360° per cycle). Every moving axis, valve, glue gun and sensor window is a curve or a window on
that chart. Mechanical design, controls and simulation all work from the same chart, so it lives in
one file (`cycle.yaml`) and everything else is generated from it. When the chart and the PLC disagree,
the chart is right and the PLC gets regenerated.

## 3. Everything is text, so an AI can work on all of it

Claude can't drive SolidWorks or MOVISUITE screens reliably. It can write and change code and data
very well. So geometry is parametric code (build123d/CadQuery), the BOM is generated, the I/O
list is data, and PLC code is IEC 61131-3 text. GUI tools stay in the loop for **viewing,
commissioning and manufacturing**, fed by files exported from the repo.

## 4. The checker is the judge, not the designer

A language model reasoning about 3D geometry and timing in its head gets plausible-looking answers
that are wrong. It puts the product down 6 mm off, fires glue into the air, or picks a speed where
the timing only works at nominal. The design is the files; the verdict comes from deterministic
checks run against those files every time anything changes. "It clears" is a claim only
`make verify` can make.

Corollaries:

- **Fix the design, never the check.** Loosening a clearance rule or tolerance to pass is a
  chief-engineer decision, recorded in git.
- **The reviewer is not the author.** At each gate, a fresh agent that did not write the design reviews it.

## 5. Simulation earns trust through measurement

Rigid-body kinematics (where things are, what collides, when valves fire) can be simulated
exactly. **Paper is a different matter.** Thin flexible sheets, air cushions, static, glue tack and
vacuum leakage through porous stock are where simulations look confident and are wrong. So:

- Every number the sim depends on records where it came from: datasheet, measured, or **assumed**.
- Every assumed number names the **cheap physical test** that will replace it.
- After calibration, a **holdout test** the sim was not tuned on checks one of its predictions.
  If it matches, the sim has earned trust in that regime. If it doesn't, you found the gap before buying steel.

## 6. Functional models before prototypes

Prove one physical effect at a time on cheap rigs (a vacuum cup on a slide, a glue valve over a
moving sheet, a 3D-printed linkage on a stepper) before building the machine. The expensive
prototype should mostly **confirm** what the calibrated model already predicted.

## 7. Catalog parts, deterministic processes

Buy nameplate components with datasheets, CAD models and spares availability. Prefer processes that
are deterministic and operator-proof: mechanical registration over operator skill, interlocks over
procedures. A custom part needs a stated reason.

## 8. The human is the chief engineer

Claude drafts, models, codes, checks and documents. The human:

- answers the process questions only someone at the machine can answer
- approves requirements and the cycle diagram, the highest-leverage review there is
- runs the physical tests
- signs off drawings before a machinist sees them
- owns safety.

## 9. Ranges, not points

Machines run at a range of speeds, on a range of stocks, at a range of temperatures. Valve and
sensor delays are fixed in **milliseconds**, so they move in **degrees** when speed changes. Every check runs at
min, nominal and max speed. A design that only works at nominal does not work.

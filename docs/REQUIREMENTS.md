# Framework requirements

Requirements for the **framework itself** (not for any machine). Status: `done` = implemented in
this repo, `doc` = defined as a rule/process in docs, `roadmap` = not yet built.

## Single source of truth

| ID | Requirement | Status |
|---|---|---|
| FR-001 | Every design fact (requirements, parameters, timing, geometry, BOM, I/O, PLC code, tests) is stored as text or code in git | doc |
| FR-002 | All project data files validate against JSON schemas in `schemas/` | done |
| FR-003 | The cycle diagram is the only place motion and valve timing are defined; PLC timing constants and sim inputs are generated from it, staleness fails verify | done (PLC GVLs) / roadmap (drive cam-table export) |
| FR-004 | The BOM carries specs, ports and connections; geometry and params reference it and are cross-checked | done (generation from CAD assembly: roadmap) |
| FR-005 | GUI tool exports (MOVISUITE, CAD viewers, test loggers) are committed back to the repo | doc |

## Verification

| ID | Requirement | Status |
|---|---|---|
| FR-010 | A single command (`make verify`) runs every check and returns a verdict and a report | done |
| FR-011 | Checks are deterministic functions of the project files | done |
| FR-012 | Every timing and product-path check runs at min, nominal and max speed | done |
| FR-013 | Motion laws checked for coverage and position/velocity continuity; acceleration steps warned | done |
| FR-014 | Peak velocity and acceleration checked against catalog drive limits at max speed | done |
| FR-015 | Planar clearance sweep over the full cycle with declared contact windows and per-pair clearances | done |
| FR-016 | Product path checked: grip at pick port before departure; release at place port within tolerance, at rest; inertial slip during carry | done |
| FR-017 | Process operations (e.g. glue) checked for location on the product, gap, and off-product deposition at all speeds | done |
| FR-018 | Requirements traceability: each requirement maps to a check, a physical test or a review; status reported | done |
| FR-019 | Assumption audit: every assumed parameter names its calibrating test; the report lists what the verdict rests on | done |
| FR-020 | A deliberately broken example demonstrates every check failing | done |
| FR-021 | Side-view render of the cycle for human review | done |
| FR-022 | 3D interference sweep on code-CAD geometry, all speeds, moving-vs-moving | done |
| FR-023 | Tolerance stack-ups, worst case and Monte Carlo | roadmap |
| FR-024 | Software-in-the-loop: the real ST program against the plant model at scan time, with fault injection | done (ST subset); real soft-PLC roadmap |
| FR-025 | Flexible sheet dynamics feeding geometry and process checks | done (FE beam); Chrono/aeroelastic roadmap |
| FR-026 | CI runs verify on every push | done |
| FR-027 | Interface compatibility between connected BOM parts | done |
| FR-028 | Axis sizing (speed, accel, stroke, payload, peak/RMS torque, rpm, inertia ratio) from BOM data | done |
| FR-029 | Project constraint rules across specs (budgets, frequencies, assumption-vs-datasheet guards) | done |
| FR-030a | I/O mapping: channel, voltage, current, safety-rating checks | done |
| FR-031a | 3D model exported (STEP, GLB) and rendered to an image on every verify | done |

## Process and roles

| ID | Requirement | Status |
|---|---|---|
| FR-030 | Every task is labelled TIER-A or TIER-B; Claude prints a model-switch banner on mismatch | doc |
| FR-031 | Gates G0–G5 are passed only by the human chief engineer | doc |
| FR-032 | An independent reviewer agent that did not author the design runs at every gate | doc (`.claude/agents/gate-reviewer.md`) |
| FR-033 | Failing checks are fixed in the design; loosening a check requires recorded human approval | doc |
| FR-034 | Catalog parts by default; custom parts carry a written reason | doc |
| FR-035 | Every physical test records cost, method, samples, result; holdout tests are never used for calibration | done (schema) |
| FR-036 | Discipline knowledge lives in skills loaded on demand, not in separate permanent agents | done |

## Outputs (per machine)

| ID | Requirement | Status |
|---|---|---|
| FR-040 | Machinist drawings with GD&T from the 3D model, released only after G4 sign-off | roadmap |
| FR-041 | Purchase list with three quotes per line for PO submission | roadmap |
| FR-042 | I/O list (done, checked against cards/devices); schematics, wire list, panel layout | partial |
| FR-043 | PLC project: generated GVLs + IEC 61131-3 code (done); drive cam tables + HMI tags (roadmap) | partial |
| FR-044 | ISO 12100 risk assessment and ISO 13849 safety-function list | roadmap (skill defines content) |
| FR-045 | Commissioning procedure and measured-vs-predicted report | roadmap |

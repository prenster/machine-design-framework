---
name: mdf-mechanical
description: Mechanical design for machine stations - planar layout, parametric code-CAD (build123d/CadQuery), catalog part selection, BOM. Use when creating or changing geometry, choosing components, or generating the bill of materials.
---
# Mechanical design  [TIER-A concept/layout, TIER-B detailing to spec]

## Order of work
1. Planar layout (`layout.yaml`) - side view, enough to run SWEEP and product-path checks. Pass verify here first.
2. 3D code-CAD (`cad/*.py`, build123d preferred): parametric, dimensions from `params.yaml`, catalog parts imported as STEP.
3. BOM generated from the assembly tree: part number, vendor, qty, catalog link, custom/catalog flag.

## Catalog first
- Linear motion, bearings, shafts, profiles, fasteners: Misumi, Bosch Rexroth, igus.
- Drives/servos: SEW-Eurodrive (MOVI-C) to match the controls stack.
- Pneumatics/vacuum: Festo, SMC, Schmalz, Piab.
- Frames: aluminium profile (80/20, Bosch, Item) for mock-ups and light stations; welded/machined steel plate for production stiffness.
- A custom part needs a one-line reason in the CAD source.

## Geometry rules
- Every body in `layout.yaml` that corresponds to a part carries `part:` so geometry, BOM and drawings stay linked.
- Never fix a clearance failure by editing a clearance rule. Move the part, change the timing, or change the mechanism.
- Design for adjustment where the process is uncertain (slotted holes, eccentric pins) and record the adjustment range as a param.
- Design for service: guard removal, belt/cup change, glue nozzle cleaning access.

## Never claim
"It fits" / "it clears" without `make verify`. If the claim is 3D and only the planar model exists, say "planar check only; 3D not verified".

---
name: mdf-process
description: Define what physically happens to the product at each machine station - product states, ports, tolerances, stock and adhesive ranges. Use before any hardware design (MDF phase 0) and whenever a requirement about the product changes.
---
# Process definition  [TIER-A]

The machine exists to move the product through a sequence of states. Define that sequence first.

## Produce
- `requirements.yaml`: process requirements (REQ-PROC-xxx), each with a verification method.
- `layout.yaml` `ports`: every place the product is picked, handed over, processed or placed, with x/z and tolerance.
- `params.yaml`: speed range, product dimensions/caliper range, and every process constant with its source.

## Ask the chief engineer (only what you can't know)
- Stock range: caliper, basis weight, grain, coated/uncoated, curl tendencies, worst stock in practice.
- Adhesive: type (PVA/hot-melt/cold glue), open time, what the current machines use.
- Product variation: size range, changeover frequency, minimum run length.
- Speed: target range and what the upstream/downstream equipment runs at.
- Current pain: what goes wrong on existing machines doing this job.

## For each station, write down
1. Input state (where the product is, how it is held, orientation, tolerance).
2. Operation (what is done to it, process window).
3. Output state.
4. **How it is held at every instant** (never "floating": gripped, on a belt, against a lay, or under a hold-down).
5. Failure modes: double, missing, skewed, jammed, glue missing, glue misplaced. How each is detected.

## Rules
- Tolerances are on the product, not the machine. Machine tolerances are derived later by stack-up.
- Every "the sheet will just..." statement is an assumption. Give it a param with `source: assumed` and a test.
- Paper behaviour (flutter, air cushion, static, separation) is not simulated reliably. Plan physical tests (`mdf-physical-tests`).

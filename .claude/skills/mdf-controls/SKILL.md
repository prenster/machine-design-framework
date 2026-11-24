---
name: mdf-controls
description: Controls design - IEC 61131-3 PLC code, SEW MOVI-C / MOVISUITE / MOVIKIT camming, CODESYS soft-PLC, cam tables generated from cycle.yaml, interlocks, fault handling, HMI tags. Use for any PLC, motion controller or drive work.
---
# Controls  [TIER-B to code an approved cycle/I-O list, TIER-A for architecture and fault strategy]

## Sources of truth
- Motion and valve timing: `cycle.yaml` only. Cam tables are generated from it. Never hand-tune cams in the drive and leave the repo stale - export and commit.
- I/O: `electrical/io_list.yaml`.

## SEW MOVI-C stack
- Motion: MOVIKIT modules (MultiMotion / Camming) - parameterize, don't program, where a module exists.
- Sequencing, interlocks, faults: IEC 61131-3 Structured Text on the MOVI-C CONTROLLER.
- MOVISUITE is GUI-only: Claude generates import files (cam tables, parameter sets, code); the human imports and commissions. Confirm import formats with SEW for the installed version.

## Program structure (every machine)
- State machine: Off -> Ready -> Running -> Stopping -> Fault, plus Jog/Setup.
- One cam master (virtual axis = machine angle); all axes and valve tracks follow it.
- Valve outputs as cam-position windows with delay compensation, recomputed from current speed.
- Product-tracking per station: present / missing / double / jammed, with sensor windows on the cycle chart.
- Fault handling: stop category per fault (IEC 60204-1 cat 0/1/2), defined in the risk assessment.
- Safety functions run on the safety controller/safety relay, not in standard PLC code.

## Verification
- SIL: run the ST code in a CODESYS soft-PLC against the model; inject faults (double sheet, missing sheet, jam, e-stop, air loss).
- Bench: generated cam table on one real servo axis on the mock-up; measure following error; feed back to params.

# Planted faults

Each is a plausible mistake: it looks fine when reasoned about, and several are invisible in a 2D side view or in
any single file. `make verify-broken` must FAIL and name every one.

| # | Fault | Where | Caught by |
|---|---|---|---|
| F1 | Place position typed 594 instead of 600 | cycle.yaml | PROD-PLACE, SWEEP-CLEARANCE, SIL-NOMINAL |
| F2 | Glue pass left at 3 mm height | cycle.yaml | GLUE-BEAD (gap 4 mm, glue on the machine) |
| F3 | Vacuum released early "to save time" | cycle.yaml | PROD-PLACE, SIL-NOMINAL (sheets dropped) |
| F4 | Glue-pass speed changed, neighbours not updated | cycle.yaml | CYC-LAW (velocity jumps) |
| F5 | Vacuum plate shortened: 40 mm unsupported overhang | layout.yaml | SHEET-DYN → SWEEP-CLEARANCE (edge drags on stack, lands early) |
| F6 | Vacuum plate widened past the sheet | cad/station.py | SWEEP-3D (plate hits side guides at pick) |
| F7 | Frame upright moved inside the carriage travel | cad/station.py | SWEEP-3D (carriage hits upright at place) |
| F8 | Z module body lengthened | cad/station.py | SWEEP-3D (bracket hits module bottom at lift) |
| F9 | "Cheaper" X motor | bom.yaml | BOM-SIZING (peak and RMS torque) |
| F10 | Ejector vacuum port M5, plate port G1/8 | bom.yaml | BOM-IFACE |
| F11 | Glue valve with 1.2 A spike coil, slower response | bom.yaml | IO-MAP (0.5 A output), C-GLUE-ASSUME-* (sim faster than the part) |
| F12 | X module swapped for a 50 m/s² model | bom.yaml | BOM-XREF (params disagree), BOM-SIZING (acceleration) |
| F13 | Guard switch wired to a standard input card | io_list.yaml | IO-MAP (safety device on non-safety input) |
| F14 | Glue condition "simplified" in the PLC (no sheet check) | plc/src/MAIN.st | SIL-MISSED-PICK, SIL-STACK-EMPTY (glue on the machine) |
| F15 | Cycle and I/O changed, PLC GVLs not regenerated | plc/generated | PLC-GEN |
